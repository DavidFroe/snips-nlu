"""Was ans Modell ging — und was davon eine Absicht werden sollte.

Die Schicht fängt heute rund 30 % der Nachrichten ab. Die übrigen 70 %
laufen durch, und niemand sieht sich an, was darin steckt. Genau das
holt dieses Werkzeug nach::

    python -m absicht.lernen logs/absicht.jsonl
    python -m absicht.lernen logs/absicht.jsonl --vorschlaege
    python -m absicht.lernen logs/absicht.jsonl --vorschlaege --einbetten

Der Bediener am 06.08.2026: *„Wie schaffen wir es, dass die Datenbank der
vorgefertigten Fragen wächst? Kannst du ein Statistik-Zeug einarbeiten,
dass wir hin und wieder mit dem System selber auswerten — an der und der
Stelle hat der Nutzer immer da und da mit geantwortet. Damit wir den
30-Prozent-Teil grösser bekommen."*

## Wie gruppiert wird

Ohne ``--einbetten`` über gemeinsame Wörter: schnell, findet aber nur,
was wörtlich ähnlich ist.

Mit ``--einbetten`` über ``bge-m3``: findet auch, was dasselbe meint und
anders heisst. Kostet rund 650 ms je Nachricht — bei zweihundert
Nachrichten also gut zwei Minuten. Deshalb nicht die Vorgabe.

## Was dieses Werkzeug nicht tut

**Es ändert nichts.** Es schlägt vor, und der Bediener entscheidet. Eine
Absicht, die sich selbst in die Datei schreibt, ist eine Absicht, die
niemand geprüft hat — und bei ``folgenreich: true`` verschickt so etwas
Bewerbungen.
"""

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


#: Ab wie vielen ähnlichen Nachrichten eine Gruppe als Vorschlag zählt.
#: Zwei sind ein Zufall, drei sind ein Muster.
AB_WIE_VIELEN = 3

#: Wortähnlichkeit, ab der zwei Nachrichten in dieselbe Gruppe kommen.
NAH_GENUG = 0.55

#: Wörter, die keine Gruppe begründen — sie stehen in jedem zweiten Satz.
FUELLWOERTER = frozenset({
    "der", "die", "das", "und", "oder", "aber", "ich", "du", "sie", "wir",
    "ist", "sind", "war", "hat", "habe", "kann", "muss", "soll", "wird",
    "mit", "von", "fuer", "auf", "aus", "bei", "nach", "vor", "noch",
    "auch", "nur", "schon", "mal", "bitte", "danke", "was", "wie", "wo",
    "den", "dem", "des", "ein", "eine", "einen", "einem", "eines", "im",
    "in", "zu", "zum", "zur", "am", "an", "es", "sich", "nicht", "kein",
})


def _normalisieren(text):
    t = unicodedata.normalize("NFC", str(text or "")).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\wäöüß\s]", " ", t)).strip()


def _kennworte(text):
    """Die Wörter eines Textes, die eine Gruppe begründen können"""
    return {w for w in _normalisieren(text).split()
            if len(w) >= 4 and w not in FUELLWOERTER}


def _naehe(einer, anderer):
    """Anteil gemeinsamer Kennworte, zwischen 0 und 1"""
    if not einer or not anderer:
        return 0.0
    return len(einer & anderer) / len(einer | anderer)


# ── Das Protokoll lesen ─────────────────────────────────────────────────

def protokoll_lesen(pfad):
    """Alle Sätze aus dem Protokoll der Schicht

    Das Protokoll hat keinen festen Ort: :mod:`absicht.protokoll` gibt
    die Sätze an das Logging des Aufrufers weiter, und wohin die gehen,
    entscheidet der Aufrufer mit :func:`absicht.protokoll.in_datei`.
    Deshalb steht der Pfad hier im Aufruf und wird nicht erraten.

    Args:
        pfad (Path): die Protokolldatei

    Returns:
        list[dict]: die Protokollsätze
    """
    saetze = []
    try:
        for zeile in Path(pfad).read_text(encoding="utf8").splitlines():
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                saetze.append(json.loads(zeile))
            except ValueError:
                continue
    except OSError:
        return []
    return saetze


def durchgereichte(saetze):
    """Die Nachrichten, für die es keine Absicht gab

    Das sind die Kandidaten: Was hier steht, hat das Modell gekostet.
    """
    return [s for s in saetze
            if str(s.get("weg", "")) == "durchreichen"
            and str(s.get("text", "")).strip()]


# ── Gruppieren ──────────────────────────────────────────────────────────

def gruppieren(texte, einbetter=None):
    """Ordnet ähnliche Nachrichten zu Gruppen

    Args:
        texte (list[str]): die zu gruppierenden Nachrichten
        einbetter (Einbetter): wenn angegeben, wird inhaltlich verglichen
            statt über gemeinsame Wörter

    Returns:
        list[list[str]]: Gruppen, die grösste zuerst
    """
    if einbetter is not None:
        return _gruppieren_inhaltlich(texte, einbetter)
    return _gruppieren_woertlich(texte)


def _gruppieren_woertlich(texte):
    offen = [(t, _kennworte(t)) for t in texte]
    offen = [(t, k) for t, k in offen if k]
    gruppen = []
    while offen:
        kopf_text, kopf_worte = offen.pop(0)
        gruppe = [kopf_text]
        rest = []
        for text, worte in offen:
            if _naehe(kopf_worte, worte) >= NAH_GENUG:
                gruppe.append(text)
            else:
                rest.append((text, worte))
        offen = rest
        gruppen.append(gruppe)
    gruppen.sort(key=len, reverse=True)
    return gruppen


def _gruppieren_inhaltlich(texte, einbetter):
    from absicht.wissen.einbetten import aehnlichkeit
    mit_vektor = []
    for text in texte:
        vektor = einbetter.einbetten(text)
        if vektor:
            mit_vektor.append((text, vektor))
    if not mit_vektor:
        # Einbetter ausgefallen — dann eben wörtlich.
        return _gruppieren_woertlich(texte)

    gruppen = []
    offen = list(mit_vektor)
    while offen:
        kopf_text, kopf_vektor = offen.pop(0)
        gruppe = [kopf_text]
        rest = []
        for text, vektor in offen:
            # 0,75 ist strenger als die Suchschwelle (0,5): Hier sollen
            # Nachrichten zusammenkommen, die *dasselbe* meinen, nicht
            # solche, die nur verwandt sind.
            if aehnlichkeit(kopf_vektor, vektor) >= 0.75:
                gruppe.append(text)
            else:
                rest.append((text, vektor))
        offen = rest
        gruppen.append(gruppe)
    gruppen.sort(key=len, reverse=True)
    return gruppen


# ── Vorschlagen ─────────────────────────────────────────────────────────

def vorschlag_bauen(gruppe):
    """Macht aus einer Gruppe einen Vorschlag für die Absichtsdatei

    Returns:
        dict: mit `anzahl`, `beispiele`, `gemeinsame_worte` und einem
            Entwurf für den YAML-Eintrag
    """
    worte = Counter()
    for text in gruppe:
        worte.update(_kennworte(text))
    # Was in mindestens der Hälfte der Nachrichten vorkommt, trägt die
    # Gruppe — das sind die Kandidaten für eine Wendung.
    tragend = [w for w, n in worte.most_common()
               if n >= max(2, len(gruppe) // 2)]
    kurze = sorted({_normalisieren(t) for t in gruppe if len(t) <= 24})
    return {
        "anzahl": len(gruppe),
        "beispiele": gruppe[:4],
        "gemeinsame_worte": tragend[:6],
        "kurzbefehle": kurze[:8],
    }


def _als_yaml(name, vorschlag):
    """Der Entwurf, wie er in absichten_de.yaml stehen könnte"""
    zeilen = ["  %s:" % name,
              "    # Vorschlag aus %d aehnlichen Nachrichten im Protokoll."
              % vorschlag["anzahl"],
              "    # GEPRUEFT: nein — Absicht, Aktion und Schwellen fehlen.",
              "    aktion: null",
              "    folgenreich: false"]
    if vorschlag["kurzbefehle"]:
        zeilen.append("    kurzbefehle:")
        zeilen += ["      - %s" % k for k in vorschlag["kurzbefehle"]]
    if vorschlag["gemeinsame_worte"]:
        zeilen.append("    wendungen:")
        zeilen.append("      - [%s]" % ", ".join(
            vorschlag["gemeinsame_worte"][:3]))
    return "\n".join(zeilen)


# ── Aufruf ──────────────────────────────────────────────────────────────

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("protokoll",
                   help="die Protokolldatei der Schicht (JSON je Zeile)")
    p.add_argument("--vorschlaege", action="store_true",
                   help="Gruppen als Entwuerfe fuer die Absichtsdatei zeigen")
    p.add_argument("--einbetten", action="store_true",
                   help="inhaltlich gruppieren statt ueber gemeinsame Woerter")
    p.add_argument("--ab", type=int, default=AB_WIE_VIELEN,
                   help="ab wie vielen Nachrichten eine Gruppe zaehlt")
    args = p.parse_args(argv)

    saetze = protokoll_lesen(args.protokoll)
    if not saetze:
        print("  %s ist leer oder nicht lesbar." % args.protokoll)
        print()
        print("  Das Protokoll entsteht erst, wenn der Aufrufer es einrichtet:")
        print("      from absicht import protokoll")
        print("      protokoll.in_datei('logs/absicht.jsonl')")
        return 1

    wege = Counter(str(s.get("weg", "?")) for s in saetze)
    gesamt = len(saetze)
    print("  %d Nachrichten im Protokoll\n" % gesamt)
    for weg in ("direkt", "aufbereitet", "durchreichen"):
        n = wege.get(weg, 0)
        print("  %-14s %5d  %3d %%" % (weg, n, n * 100 // gesamt if gesamt else 0))

    offen = durchgereichte(saetze)
    if not offen:
        print("\n  Nichts durchgereicht — es gibt nichts zu lernen.")
        return 0

    print("\n  %d Nachrichten gingen ans Modell. Was steckt darin?\n" % len(offen))

    einbetter = None
    if args.einbetten:
        einbetter = _einbetter_bauen()
        if einbetter is None:
            print("  (Kein Einbetter erreichbar — gruppiere ueber Woerter.)\n")

    gruppen = [g for g in gruppieren([s["text"] for s in offen], einbetter)
               if len(g) >= args.ab]
    if not gruppen:
        print("  Keine Gruppe mit mindestens %d aehnlichen Nachrichten." % args.ab)
        print("  Das heisst: die durchgereichten Nachrichten sind jede fuer")
        print("  sich verschieden. Genau dafuer ist das Modell da.")
        return 0

    for nummer, gruppe in enumerate(gruppen, 1):
        vorschlag = vorschlag_bauen(gruppe)
        print("  ── Gruppe %d — %d Nachrichten" % (nummer, vorschlag["anzahl"]))
        if vorschlag["gemeinsame_worte"]:
            print("     gemeinsam: %s" % ", ".join(vorschlag["gemeinsame_worte"]))
        for beispiel in vorschlag["beispiele"]:
            print("     · %s" % beispiel[:66])
        if args.vorschlaege:
            print()
            print(_als_yaml("absicht_%d" % nummer, vorschlag))
        print()

    print("  Diese Entwuerfe schreibt niemand automatisch in die")
    print("  Absichtsdatei. Absicht, Aktion und Schwellen gehoeren geprueft —")
    print("  eine Absicht mit `folgenreich: true` verschickt Bewerbungen.")
    return 0


def _einbetter_bauen():
    """Holt den Proxy-Einbetter aus owltrail.conf, falls vorhanden"""
    from absicht.wissen.einbetten import ProxyEinbetter
    for kandidat in (Path.cwd() / "owltrail.conf",
                     Path.home() / "bewerbungstrainer" / "owltrail.conf"):
        try:
            konf = json.loads(kandidat.read_text(encoding="utf8"))
        except (OSError, ValueError):
            continue
        return ProxyEinbetter(
            url="http://%s:%s" % (konf.get("server_ip", "127.0.0.1"),
                                  konf.get("quiteque_port", 7077)),
            token=konf.get("token", ""),
            nutzer=konf.get("username", ""))
    return None


if __name__ == "__main__":
    sys.exit(main())
