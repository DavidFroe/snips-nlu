"""Vom Treffer zum Weg — und die Regeln, die dabei nicht verhandelbar sind.

Drei Wege, mehr nicht:

``direkt``
    Wir antworten selbst. Kein Modell, keine 2.800 Token, keine zwei Minuten
    Wartezeit.
``aufbereitet``
    Das Modell wird gebraucht, aber wir wissen wofuer. Der Aufrufer bekommt
    einen Bauplan, welche Prompt-Bausteine noetig sind und welche er
    weglassen kann.
``durchreichen``
    Keine Ahnung. Voller Kontext ans Modell, wie bisher.

Die Schwellen stehen in :mod:`absicht.konfiguration`. Zwei Regeln stehen
darueber und lassen sich nicht wegkonfigurieren, weil an ihnen der teuerste
Fehler dieses Systems haengt — siehe :func:`entscheiden`.
"""

WEG_DIREKT = "direkt"
WEG_AUFBEREITET = "aufbereitet"
WEG_DURCHREICHEN = "durchreichen"


def entscheiden(treffer, kontext, nutzer, absichten, antworten,
                konfiguration):
    """Waehlt den Weg fuer die beste erkannte Absicht

    Die Reihenfolge der Pruefungen ist die Aussage dieses Moduls:

    1. Ohne Treffer oder unter der untersten Schwelle geht alles durch.
    2. **Ohne ``letzte_frage`` ist ein "ja" bedeutungslos** — dann
       durchreichen, egal wie sicher die Erkennung war. Wer nichts gefragt
       hat, bekommt keine Antwort auf eine Frage.
    3. **Bei ``offener_dialog`` nie ``direkt`` fuer eine Absicht mit
       Aktion.** Ein Bewerber, der mitten im Freitextgespraech "Ja" schreibt,
       meint das Gespraech, nicht die Freigabe. Deutet die Schicht das als
       Freigabe, geht eine Bewerbung raus, die niemand freigegeben hat.
    4. Fehlt der Bezug, ist eine Aktion nicht anwendbar.
    5. Erst danach entscheidet die Sicherheit gegen die Schwelle — 0,95 statt
       0,80, wenn die Absicht Folgen hat.

    Args:
        treffer (list[Treffer]): absteigend sortiert, darf leer sein
        kontext (dict): was der Aufrufer weiss
        nutzer (str): wer schreibt; steht Antworten als Platzhalter zur
            Verfuegung
        absichten (dict[str, Absicht]): die Absichtsdefinitionen
        antworten (Antwortbibliothek): die Textbausteine
        konfiguration (Konfiguration): die Schwellen

    Returns:
        tuple[dict, dict]: das Ergebnis nach aussen und die Begruendungen
            fuers Protokoll
    """
    kontext = kontext or dict()
    spuren = []

    if not treffer:
        return _durchreichen(0.0), _spur(spuren, "keine Absicht erkannt")

    bester = treffer[0]
    definition = absichten[bester.absicht]
    sicherheit = bester.sicherheit
    spuren.append(bester.begruendung)

    if sicherheit < konfiguration.schwelle_aufbereitet:
        return _durchreichen(sicherheit), _spur(
            spuren, "Sicherheit %.2f unter der Schwelle %.2f"
            % (sicherheit, konfiguration.schwelle_aufbereitet))

    if definition.braucht_letzte_frage and not kontext.get("letzte_frage"):
        return _durchreichen(sicherheit), _spur(
            spuren, "'%s' braucht eine vorangegangene Frage, es steht aber "
                    "keine im Kontext" % definition.name)

    direkt_erlaubt = True
    if kontext.get("offener_dialog") and definition.aktion:
        direkt_erlaubt = False
        spuren.append(
            "offener Dialog: '%s' traegt die Aktion '%s' und darf hier nicht "
            "direkt beantwortet werden" % (definition.name, definition.aktion))
    if definition.braucht_bezug and not kontext.get("ref"):
        direkt_erlaubt = False
        spuren.append(
            "'%s' braucht einen Bezug, im Kontext steht keine ref"
            % definition.name)

    schwelle = (konfiguration.schwelle_folgenreich if definition.folgenreich
                else konfiguration.schwelle_direkt)

    if direkt_erlaubt and sicherheit >= schwelle:
        werte = _werte(kontext, nutzer)
        antwort = antworten.waehlen(definition.name, werte)
        if antwort is not None:
            return _direkt(definition, sicherheit, antwort, kontext), _spur(
                spuren, "Sicherheit %.2f erreicht die Schwelle %.2f"
                % (sicherheit, schwelle))
        spuren.append("keine anwendbare Antwort hinterlegt")
    elif direkt_erlaubt:
        spuren.append("Sicherheit %.2f unter der Schwelle %.2f fuer '%s'"
                      % (sicherheit, schwelle, definition.name))

    if not definition.llm_auftrag:
        return _durchreichen(sicherheit), _spur(
            spuren, "kein Auftrag fuer das Modell hinterlegt, also voller "
                    "Kontext")

    return _aufbereitet(definition, sicherheit, bester), _spur(
        spuren, "Modell noetig, Auftrag steht fest")


def _direkt(definition, sicherheit, antwort, kontext):
    ergebnis = {
        "weg": WEG_DIREKT,
        "absicht": definition.name,
        "sicherheit": sicherheit,
        "antwort": antwort,
        "aktion": None,
    }
    if definition.aktion:
        aktion = {"art": definition.aktion}
        if kontext.get("ref"):
            aktion["ref"] = kontext["ref"]
        ergebnis["aktion"] = aktion
    return ergebnis


def _aufbereitet(definition, sicherheit, treffer):
    auftrag = dict(definition.llm_auftrag)
    auftrag["extrakt"] = dict(treffer.extrakt)
    return {
        "weg": WEG_AUFBEREITET,
        "absicht": definition.name,
        "sicherheit": sicherheit,
        "llm_auftrag": auftrag,
    }


def _durchreichen(sicherheit):
    """Der dritte Fall

    ``absicht`` bleibt leer, weil der Aufrufer hier nichts anzuwenden hat.
    ``sicherheit`` ist die Sicherheit der *Erkennung* — sie kann hoch sein,
    obwohl durchgereicht wird, naemlich dann, wenn eine der Regeln oben den
    kurzen Weg gesperrt hat. Warum, steht im Protokoll.
    """
    return {
        "weg": WEG_DURCHREICHEN,
        "absicht": "",
        "sicherheit": sicherheit,
    }


def _werte(kontext, nutzer):
    """Was zum Fuellen von Platzhaltern zur Verfuegung steht"""
    werte = {name: wert for name, wert in kontext.items() if wert is not None}
    if nutzer:
        werte.setdefault("nutzer", nutzer)
    return werte


def _spur(spuren, letzter_grund):
    spuren.append(letzter_grund)
    return {"gruende": [s for s in spuren if s]}
