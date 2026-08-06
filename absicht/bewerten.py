"""Die Schicht an echten Nachrichten messen.

Der Nachweis aus dem Auftrag: Die Nachrichten aus den Verlaeufen laufen durch,
die eindeutigen Kurzbefehle sind richtig zugeordnet, und **keine einzige
Ablehnung wird als Zustimmung gelesen**. Dasselbe Werkzeug misst spaeter die
portierte Engine — an denselben Nachrichten, mit denselben Zahlen.

Eingabe ist eine Datei mit einer Nachricht je Zeile als JSON::

    {"text": "Nein bitte die andere zuerst", "absicht": "ablehnung",
     "kontext": {"ref": "0096"}}

``kontext`` ist freiwillig. ``absicht`` leer oder fehlend heisst: hier ist
keine Absicht zu erkennen, die Schicht soll durchreichen.

Aufruf::

    python -m absicht.bewerten nachrichten.jsonl
    python -m absicht.bewerten nachrichten.jsonl --fehler
    python -m absicht.bewerten nachrichten.jsonl --erkenner snips
    python -m absicht.bewerten nachrichten.jsonl --vergleich

``--vergleich`` laesst beide Erkenner ueber dieselben Nachrichten laufen und
stellt sie nebeneinander. Das ist der Nachweis aus Schritt 3 des Auftrags:
Die Engine bleibt nur, wenn sie das Woerterbuch schlaegt.
"""

import argparse
import json
import sys
import time
from collections import Counter

import absicht

# Was ein Modellaufruf heute kostet, gemessen am 06.08.2026: Systemprompt,
# Werkzeugbeschreibungen und Persona ergeben rund 11.000 Zeichen.
TOKEN_JE_NACHRICHT = 2800
# Der Weg "aufbereitet" laesst Werkzeugliste, Bewerbungsuebersicht und
# Verhaltensregeln weg — nach der Schaetzung im Anforderungsdokument zwei
# Drittel weniger Prompt bei gleicher Antwortguete.
ERSPARNIS_AUFBEREITET = 2.0 / 3.0


def lesen(pfad):
    """Liest die annotierten Nachrichten"""
    nachrichten = []
    with open(pfad, encoding="utf8") as datei:
        for nummer, zeile in enumerate(datei, start=1):
            zeile = zeile.strip()
            if not zeile or zeile.startswith("#"):
                continue
            try:
                eintrag = json.loads(zeile)
            except ValueError as fehler:
                raise ValueError("Zeile %d ist kein JSON: %s"
                                 % (nummer, fehler))
            nachrichten.append({
                "text": eintrag.get("text", ""),
                "absicht": eintrag.get("absicht") or "",
                "kontext": eintrag.get("kontext") or dict(),
                "nutzer": eintrag.get("nutzer"),
            })
    return nachrichten


def bewerten(nachrichten, schicht=None):
    """Laesst alle Nachrichten durch die Schicht laufen

    Returns:
        dict: Zahlen zum Ausgeben, samt der Liste der Fehler
    """
    schicht = schicht or absicht.Schicht.laden()

    richtig = 0
    wege = Counter()
    je_absicht = dict()
    fehler = []
    gefaehrlich = []
    zeiten = []

    for eintrag in nachrichten:
        beginn = time.perf_counter()
        ergebnis = schicht.pruefen(
            eintrag["text"], nutzer=eintrag["nutzer"],
            kontext=eintrag["kontext"], mit_protokoll=True)
        zeiten.append(time.perf_counter() - beginn)

        erwartet = eintrag["absicht"]
        erkannt = ergebnis["absicht"]
        wege[ergebnis["weg"]] += 1

        zahlen = je_absicht.setdefault(
            erwartet or "(keine)", {"anzahl": 0, "richtig": 0})
        zahlen["anzahl"] += 1

        if erkannt == erwartet:
            richtig += 1
            zahlen["richtig"] += 1
        else:
            fehler.append({
                "text": eintrag["text"],
                "erwartet": erwartet or "(keine)",
                "erkannt": erkannt or "(keine)",
                "sicherheit": ergebnis["sicherheit"],
                "gruende": ergebnis["protokoll"]["gruende"],
            })
            if erwartet == "ablehnung" and erkannt == "zustimmung":
                gefaehrlich.append(eintrag["text"])

    anzahl = len(nachrichten) or 1
    gespart = (wege["direkt"] * TOKEN_JE_NACHRICHT
               + wege["aufbereitet"] * TOKEN_JE_NACHRICHT
               * ERSPARNIS_AUFBEREITET)

    return {
        "anzahl": len(nachrichten),
        "richtig": richtig,
        "trefferquote": richtig / anzahl,
        "wege": wege,
        "je_absicht": je_absicht,
        "fehler": fehler,
        "gefaehrlich": gefaehrlich,
        "zeit_schnitt": sum(zeiten) / anzahl,
        "zeit_langsamste": max(zeiten) if zeiten else 0.0,
        "token_gespart": int(gespart),
        "token_gesamt": len(nachrichten) * TOKEN_JE_NACHRICHT,
    }


def ausgeben(ergebnis, mit_fehlern=False):
    """Schreibt den Bericht nach stdout"""
    print("Nachrichten           %d" % ergebnis["anzahl"])
    print("Richtig zugeordnet    %d (%.0f %%)"
          % (ergebnis["richtig"], ergebnis["trefferquote"] * 100))
    print()

    print("Wege")
    for weg in ("direkt", "aufbereitet", "durchreichen"):
        anzahl = ergebnis["wege"][weg]
        anteil = anzahl / (ergebnis["anzahl"] or 1) * 100
        print("  %-14s %4d  %3.0f %%" % (weg, anzahl, anteil))
    print()

    print("Je Absicht")
    for name in sorted(ergebnis["je_absicht"]):
        zahlen = ergebnis["je_absicht"][name]
        anteil = zahlen["richtig"] / (zahlen["anzahl"] or 1) * 100
        print("  %-22s %3d / %3d  %3.0f %%"
              % (name, zahlen["richtig"], zahlen["anzahl"], anteil))
    print()

    print("Antwortzeit           %.2f ms im Schnitt, %.2f ms die langsamste"
          % (ergebnis["zeit_schnitt"] * 1000,
             ergebnis["zeit_langsamste"] * 1000))
    print("Token gespart         %d von %d (%.0f %%)"
          % (ergebnis["token_gespart"], ergebnis["token_gesamt"],
             ergebnis["token_gespart"] / (ergebnis["token_gesamt"] or 1) * 100))
    print()

    if ergebnis["gefaehrlich"]:
        print("ABBRUCH: %d Ablehnungen wurden als Zustimmung gelesen"
              % len(ergebnis["gefaehrlich"]))
        for text in ergebnis["gefaehrlich"]:
            print("  %r" % text)
        print()
    else:
        print("Keine Ablehnung wurde als Zustimmung gelesen.")
        print()

    if mit_fehlern and ergebnis["fehler"]:
        print("Abweichungen")
        for fehler in ergebnis["fehler"]:
            print("  %r" % fehler["text"])
            print("      erwartet %s, erkannt %s (%.2f)"
                  % (fehler["erwartet"], fehler["erkannt"],
                     fehler["sicherheit"]))
            for grund in fehler["gruende"]:
                print("      - %s" % grund)


def schicht_bauen(name):
    """Baut die Schicht mit dem gewuenschten Erkenner darunter"""
    if name == "woerterbuch":
        return absicht.Schicht.laden()
    if name == "snips":
        from absicht.erkenner.snips import SnipsErkenner

        vorlage = absicht.Schicht.laden()
        erkenner = SnipsErkenner.trainieren(vorlage.absichten,
                                            random_state=42)
        return absicht.Schicht.laden(erkenner=erkenner)
    raise ValueError("Unbekannter Erkenner: %s" % name)


def vergleichen(nachrichten):
    """Laesst beide Erkenner ueber dieselben Nachrichten laufen"""
    ergebnisse = dict()
    for name in ("woerterbuch", "snips"):
        try:
            ergebnisse[name] = bewerten(nachrichten, schicht_bauen(name))
        except Exception as fehler:  # pylint: disable=broad-except
            print("%s uebersprungen: %s" % (name, fehler))
    return ergebnisse


def gegenueberstellen(ergebnisse):
    """Stellt die Erkenner nebeneinander"""
    namen = list(ergebnisse)
    print("%-24s %s" % ("", "  ".join("%12s" % n for n in namen)))
    zeilen = [
        ("Richtig zugeordnet", lambda e: "%d (%.0f %%)"
         % (e["richtig"], e["trefferquote"] * 100)),
        ("davon direkt", lambda e: str(e["wege"]["direkt"])),
        ("davon aufbereitet", lambda e: str(e["wege"]["aufbereitet"])),
        ("davon durchgereicht", lambda e: str(e["wege"]["durchreichen"])),
        ("Token gespart", lambda e: "%.0f %%"
         % (e["token_gespart"] / (e["token_gesamt"] or 1) * 100)),
        ("Zeit je Aufruf", lambda e: "%.2f ms" % (e["zeit_schnitt"] * 1000)),
        ("Ablehnung als Zustimmung", lambda e: str(len(e["gefaehrlich"]))),
    ]
    for beschriftung, wert in zeilen:
        print("%-24s %s" % (beschriftung,
                            "  ".join("%12s" % wert(ergebnisse[n])
                                      for n in namen)))
    print()
    if len(namen) == 2:
        besser = max(namen, key=lambda n: ergebnisse[n]["trefferquote"])
        gleich = (ergebnisse[namen[0]]["trefferquote"]
                  == ergebnisse[namen[1]]["trefferquote"])
        if gleich:
            print("Gleichstand — dann bleibt das Woerterbuch.")
        else:
            print("Besser: %s" % besser)


def main(argumente=None):
    zerleger = argparse.ArgumentParser(
        description="Misst die Absichtsschicht an annotierten Nachrichten")
    zerleger.add_argument(
        "datei", help="JSONL mit text, absicht und optional kontext")
    zerleger.add_argument(
        "--fehler", action="store_true",
        help="jede Abweichung einzeln auflisten, mit Begruendung")
    zerleger.add_argument(
        "--erkenner", default="woerterbuch",
        choices=("woerterbuch", "snips"),
        help="was unter der Schnittstelle arbeitet")
    zerleger.add_argument(
        "--vergleich", action="store_true",
        help="beide Erkenner nebeneinander stellen")
    gewaehlt = zerleger.parse_args(argumente)

    nachrichten = lesen(gewaehlt.datei)

    if gewaehlt.vergleich:
        ergebnisse = vergleichen(nachrichten)
        gegenueberstellen(ergebnisse)
        return 1 if any(e["gefaehrlich"] for e in ergebnisse.values()) else 0

    ergebnis = bewerten(nachrichten, schicht_bauen(gewaehlt.erkenner))
    ausgeben(ergebnis, mit_fehlern=gewaehlt.fehler)
    # Ein falsch gelesenes Ja ist ein Abbruchgrund, keine Fussnote.
    return 1 if ergebnis["gefaehrlich"] else 0


if __name__ == "__main__":
    sys.exit(main())
