"""Text auf eine vergleichbare Form bringen.

Die Nachrichten kommen aus WhatsApp, Telegram und einem Webportal. Sie sind
klein geschrieben oder GROSS, enthalten Emojis, doppelte Satzzeichen und
Tippfehler. Was hier nicht geglaettet wird, muss der Erkenner spaeter als
Unterschied verkraften — deshalb wird hier grosszuegig geglaettet und die
Toleranz gegen Tippfehler bleibt dem Erkenner ueberlassen.

Umlaute werden aufgeloest (ae, oe, ue, ss). Das kostet nichts und faengt die
Haelfte der Schreibvarianten ab: "loeschen" und "löschen" sind danach
dasselbe Wort, und "muß" wird zu "muss".
"""

import re
import unicodedata

_UMLAUTE = (
    ("ä", "ae"), ("ö", "oe"), ("ü", "ue"),
    ("Ä", "ae"), ("Ö", "oe"), ("Ü", "ue"),
    ("ß", "ss"),
)

# Alles, was kein Buchstabe, keine Ziffer und kein Leerzeichen ist. Das
# entfernt Satzzeichen und Emojis in einem Zug.
_KEIN_WORT = re.compile(r"[^\w\s]", flags=re.UNICODE)
_MEHRFACH_LEER = re.compile(r"\s+")
# Gedehnte Schreibweisen: "neeeein", "jaaaa", "hallooooo" — mehr als zwei
# gleiche Buchstaben hintereinander tragen keine Bedeutung.
_DEHNUNG = re.compile(r"(.)\1{2,}")


def normalisieren(text):
    """Gibt die vergleichbare Form eines Textes zurueck

    Args:
        text (str): Rohtext, so wie er beim Bot ankommt

    Returns:
        str: klein geschrieben, ohne Satzzeichen und Emojis, ohne Umlaute,
            ohne gedehnte Buchstaben, mit einfachen Leerzeichen
    """
    # Was kein Text ist, kann die Schicht nicht beurteilen — dann gilt, was
    # immer im Zweifel gilt: durchreichen. Ein Aufrufer, der versehentlich
    # ein dict schickt, soll keinen Bot zum Absturz bringen.
    if not text or not isinstance(text, str):
        return ""

    text = unicodedata.normalize("NFC", text)
    for umlaut, ersatz in _UMLAUTE:
        text = text.replace(umlaut, ersatz)
    text = text.lower()
    # Nach dem Kleinschreiben, damit "AE" aus einem Umlaut nicht doppelt
    # behandelt wird.
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = _KEIN_WORT.sub(" ", text)
    text = _DEHNUNG.sub(r"\1\1", text)
    return _MEHRFACH_LEER.sub(" ", text).strip()


def zerlegen(text):
    """Zerlegt einen bereits normalisierten Text in Woerter

    Args:
        text (str): Ergebnis von :func:`normalisieren`

    Returns:
        list[str]: die Woerter, in der Reihenfolge des Textes
    """
    if not text:
        return []
    return text.split(" ")
