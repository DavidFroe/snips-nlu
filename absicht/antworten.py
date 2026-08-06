"""Die Antwortbibliothek.

Die Texte stehen nicht im Code, sondern in einer YAML-Datei je Sprache. Der
Bediener pflegt sie, ohne einen Entwickler zu rufen.

Zwei Regeln haengen daran:

* **Mehrere Antworten je Absicht, zufaellig gewaehlt.** Ein System, das auf
  "danke" immer denselben Satz sagt, wird nach dem dritten Mal als Maschine
  erkannt — und der Bewerber hoert auf zu schreiben.
* **Platzhalter werden gefuellt, nicht gebaut.** Eine Antwort darf auf
  ``{portal}/bewerbung/{ref}/unterlagen`` verweisen. Fehlt einer der Werte im
  Kontext, faellt diese Antwort weg und eine andere kommt zum Zug. Halbe
  Saetze mit ``{ref}`` darin gehen nicht raus.
"""

import random
import string

import yaml


class Antwortbibliothek:
    """Haelt die Antworttexte einer Sprache"""

    def __init__(self, antworten, zufall=None):
        """
        Args:
            antworten (dict[str, list[str]]): Texte je Absicht
            zufall (random.Random, optional): eigene Quelle, damit Tests
                vorhersagbar bleiben
        """
        self.antworten = {
            name: tuple(texte or ()) for name, texte in antworten.items()}
        self.zufall = zufall or random.Random()

    @classmethod
    def laden(cls, pfad, zufall=None):
        """Liest eine ``antworten_<sprache>.yaml``"""
        with open(pfad, encoding="utf8") as datei:
            roh = yaml.safe_load(datei) or dict()
        return cls(roh, zufall=zufall)

    def hat_antwort(self, absicht):
        return bool(self.antworten.get(absicht))

    def waehlen(self, absicht, werte):
        """Sucht eine Antwort, deren Platzhalter sich fuellen lassen

        Args:
            absicht (str): Name der Absicht
            werte (dict): was zum Fuellen zur Verfuegung steht, in aller Regel
                der Kontext des Aufrufers

        Returns:
            str: der fertige Text, oder ``None``, wenn es keine brauchbare
                Antwort gibt
        """
        moegliche = [
            text for text in self.antworten.get(absicht, ())
            if _platzhalter(text).issubset(werte)]
        if not moegliche:
            return None
        return self.zufall.choice(moegliche).format(**werte)


def _platzhalter(text):
    """Welche Namen in geschweiften Klammern der Text braucht"""
    return {
        name for _, name, _, _ in string.Formatter().parse(text)
        if name}
