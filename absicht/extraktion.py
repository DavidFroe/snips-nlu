"""Was sich aus dem Text herauslesen laesst, ohne ihn zu verstehen.

Der wertvollste Weg ist "aufbereitet": Das Modell wird gerufen, aber es
bekommt nur, was es fuer diese eine Aufgabe braucht. Je mehr davon hier schon
feststeht, desto kleiner faellt der Prompt aus. "Der letzte Absatz ist mir zu
lang" traegt zwei brauchbare Angaben — welche Stelle, welcher Wunsch — und
beide stehen woertlich im Text.

Alles hier ist bewusst simpel: Wortlisten, kein Parser. Was nicht sicher
erkannt wird, fehlt lieber, als dass es geraten wird.
"""

import re

# Welche Stelle im Anschreiben gemeint ist.
_STELLEN = (
    (("letzter absatz", "letzten absatz", "der letzte absatz",
      "den letzten absatz"), "letzter Absatz"),
    (("erster absatz", "ersten absatz"), "erster Absatz"),
    (("zweiter absatz", "zweiten absatz"), "zweiter Absatz"),
    (("einleitung", "einleitungssatz"), "Einleitung"),
    (("schlusssatz", "schluss", "letzter satz", "letzten satz"), "Schluss"),
    (("betreff", "betreffzeile"), "Betreff"),
    (("anrede",), "Anrede"),
    (("absatz",), "Absatz"),
    (("anschreiben",), "Anschreiben"),
)

# Was daran geaendert werden soll.
_WUENSCHE = (
    (("zu lang", "kuerzer", "kuerzen", "kurzer", "straffen"), "kuerzer"),
    (("zu kurz", "laenger", "ausfuehrlicher"), "laenger"),
    (("foermlicher", "formeller", "seriooeser", "sachlicher"), "foermlicher"),
    (("lockerer", "legerer", "persoenlicher"), "lockerer"),
    (("umschreiben", "neu formulieren", "anders formulieren", "neu schreiben",
      "anders schreiben"), "neu formulieren"),
    (("weg", "raus", "streichen", "loeschen"), "streichen"),
)

# "10 A nicht 10 KW" — links steht, was stimmt, rechts, was falsch ist.
_KORREKTUR = re.compile(
    r"^(?P<richtig>.{1,60}?)\s+nicht\s+(?P<falsch>.{1,60})$",
    flags=re.IGNORECASE | re.DOTALL)
# "150 Ampere statt 15" — hier ist es andersherum.
_KORREKTUR_STATT = re.compile(
    r"^(?P<richtig>.{1,60}?)\s+statt\s+(?P<falsch>.{1,60})$",
    flags=re.IGNORECASE | re.DOTALL)


def auslesen(absicht, text, normalisiert):
    """Liest die Angaben aus, die zu dieser Absicht gehoeren

    Args:
        absicht (str): Name der erkannten Absicht
        text (str): Rohtext, fuer lesbare Werte im Ergebnis
        normalisiert (str): geglaettete Form, fuer den Abgleich

    Returns:
        dict: kann leer sein. Was nicht sicher erkannt wird, fehlt.
    """
    if absicht == "anschreiben_aendern":
        return _textaenderung(normalisiert)
    if absicht == "fachkorrektur":
        return _fachkorrektur(text)
    return dict()


def _textaenderung(normalisiert):
    ergebnis = dict()
    for schreibweisen, name in _STELLEN:
        if any(s in normalisiert for s in schreibweisen):
            ergebnis["stelle"] = name
            break
    for schreibweisen, name in _WUENSCHE:
        if any(s in normalisiert for s in schreibweisen):
            ergebnis["wunsch"] = name
            break
    return ergebnis


def _fachkorrektur(text):
    zusammengezogen = " ".join(text.split())
    for muster in (_KORREKTUR, _KORREKTUR_STATT):
        gefunden = muster.match(zusammengezogen)
        if gefunden:
            return {
                "richtig": gefunden.group("richtig").strip(" .,;:!?"),
                "falsch": gefunden.group("falsch").strip(" .,;:!?"),
            }
    return dict()
