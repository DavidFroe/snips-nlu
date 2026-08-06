"""Die Stellschrauben der Schicht.

Alle Schwellen stehen hier und nicht im Code, weil sie sich im Betrieb
verschieben werden. Der Schattenbetrieb liefert die Zahlen, an denen sie
nachgezogen werden.
"""

from dataclasses import dataclass
from pathlib import Path

DATEN_VERZEICHNIS = Path(__file__).parent / "daten"


@dataclass(frozen=True)
class Konfiguration:
    """Schwellen und Grenzwerte der Absichtsschicht

    Attributes:
        schwelle_direkt: ab hier antwortet die Schicht selbst, sofern eine
            Antwort hinterlegt ist
        schwelle_aufbereitet: ab hier wird das Modell mit vorbereitetem
            Auftrag gerufen; darunter geht alles durch
        schwelle_folgenreich: gilt statt ``schwelle_direkt`` fuer Absichten
            mit Folgen (abschicken, verwerfen, freigeben). Wer etwas loescht
            oder verschickt, soll sich sicher sein.
        aehnlichkeit_wort: ab welcher Aehnlichkeit zwei Woerter als dasselbe
            gelten. 0,82 laesst "ncohmal" auf "nochmal" fallen, haelt aber
            "kein" von "nein" fern.
        aehnlichkeit_nachricht: dasselbe fuer den Abgleich der ganzen
            Nachricht gegen einen Kurzbefehl
        mindestlaenge_unscharf: kuerzere Woerter muessen exakt stimmen. Bei
            drei Buchstaben ist jeder zweite Tippfehler ein anderes Wort.
        sprache: welche Datendateien geladen werden
        datenverzeichnis: wo Absichten und Antworten liegen
    """

    schwelle_direkt: float = 0.80
    schwelle_aufbereitet: float = 0.50
    schwelle_folgenreich: float = 0.95

    aehnlichkeit_wort: float = 0.82
    aehnlichkeit_nachricht: float = 0.80
    mindestlaenge_unscharf: int = 4

    sprache: str = "de"
    datenverzeichnis: Path = DATEN_VERZEICHNIS

    def absichten_datei(self):
        return self.datenverzeichnis / ("absichten_%s.yaml" % self.sprache)

    def antworten_datei(self):
        return self.datenverzeichnis / ("antworten_%s.yaml" % self.sprache)
