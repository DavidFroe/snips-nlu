"""Die Absichtsdefinitionen, so wie sie aus der YAML-Datei kommen."""

from dataclasses import dataclass, field

import yaml

from absicht.normalisierung import normalisieren, zerlegen


@dataclass(frozen=True)
class Wendung:
    """Eine Wortgruppe, die im Text vorkommen muss — alle Woerter davon

    Attributes:
        woerter: normalisierte Woerter, Reihenfolge egal
        sicherheit: vom Bediener vorgegebener Wert; ``None`` heisst, dass er
            aus der Laenge der Wortgruppe berechnet wird
    """

    woerter: tuple
    sicherheit: float = None


@dataclass(frozen=True)
class Absicht:
    """Was die Schicht ueber eine Absicht weiss

    Attributes:
        name: Bezeichner, wie er nach aussen gegeben wird
        aktion: was der Aufrufer tun soll, oder ``None`` fuer "nur antworten"
        folgenreich: verschickt, loescht oder gibt frei — braucht 0,95
        braucht_bezug: ohne ``ref`` im Kontext nicht anwendbar
        braucht_letzte_frage: ohne ``letzte_frage`` im Kontext bedeutungslos
        verneinung_schliesst_aus: eine Verneinung in der Nachricht macht diese
            Absicht unmoeglich. Steht bei der Zustimmung — ein falsch
            gelesenes Ja ist der teuerste Fehler, den dieses System machen
            kann.
        kurzbefehle: normalisierte Nachrichten, die genau so lauten
        wendungen: Wortgruppen fuer den laengeren Text
        llm_auftrag: Bauplan fuer den Weg "aufbereitet"
    """

    name: str
    aktion: str = None
    folgenreich: bool = False
    braucht_bezug: bool = False
    braucht_letzte_frage: bool = False
    verneinung_schliesst_aus: bool = False
    kurzbefehle: tuple = ()
    wendungen: tuple = ()
    llm_auftrag: dict = field(default_factory=dict)


def laden(pfad):
    """Liest die Absichtsdefinitionen einer Sprache

    Args:
        pfad (Path): Pfad auf eine ``absichten_<sprache>.yaml``

    Returns:
        tuple[dict[str, Absicht], frozenset[str]]: die Absichten nach Namen
            und die Verneinungswoerter dieser Sprache
    """
    with open(pfad, encoding="utf8") as datei:
        roh = yaml.safe_load(datei)

    verneinung = frozenset(
        normalisieren(wort) for wort in roh.get("verneinung", []))

    absichten = dict()
    for name, eintrag in (roh.get("absichten") or dict()).items():
        eintrag = eintrag or dict()
        absichten[name] = Absicht(
            name=name,
            aktion=eintrag.get("aktion"),
            folgenreich=bool(eintrag.get("folgenreich", False)),
            braucht_bezug=bool(eintrag.get("braucht_bezug", False)),
            braucht_letzte_frage=bool(
                eintrag.get("braucht_letzte_frage", False)),
            verneinung_schliesst_aus=bool(
                eintrag.get("verneinung_schliesst_aus", False)),
            kurzbefehle=tuple(
                normalisieren(k) for k in eintrag.get("kurzbefehle") or []),
            wendungen=tuple(
                _wendung_lesen(w) for w in eintrag.get("wendungen") or []),
            llm_auftrag=dict(eintrag.get("llm_auftrag") or dict()),
        )
    return absichten, verneinung


def _wendung_lesen(eintrag):
    """Nimmt beide Schreibweisen aus der YAML-Datei entgegen

    Die kurze Form ist eine Liste von Woertern, die ausfuehrliche ein
    Abschnitt mit ``woerter`` und einer eigenen ``sicherheit``.
    """
    if isinstance(eintrag, dict):
        woerter = eintrag.get("woerter") or []
        sicherheit = eintrag.get("sicherheit")
    else:
        woerter = eintrag
        sicherheit = None

    normalisiert = []
    for wort in woerter:
        normalisiert.extend(zerlegen(normalisieren(str(wort))))
    return Wendung(woerter=tuple(normalisiert), sicherheit=sicherheit)
