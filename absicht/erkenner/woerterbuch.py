"""Erkennung ueber ein Woerterbuch, mit ``difflib`` gegen Tippfehler.

Das ist der Vergleichsmassstab: Wenn eine trainierte Engine kommt, muss sie
besser sein als diese Wortliste — an denselben Nachrichten gemessen. Ist sie
es nicht, bleibt die Wortliste, und niemand hat etwas verloren.

Wie bewertet wird, in absteigender Staerke:

1. Die ganze Nachricht *ist* ein Kurzbefehl ("nein", "JO", "danke").
   Das ist der Fall, der die 2.800 Token einspart, und er ist eindeutig.
2. Die ganze Nachricht ist einem Kurzbefehl aehnlich genug ("neee", "hallo").
3. Die Nachricht *beginnt* mit einem Kurzbefehl ("Nein bitte die andere
   zuerst"). Wer antwortet, stellt die Antwort voran.
4. Eine hinterlegte Wortgruppe kommt vor ("absatz" und "lang"). Das reicht
   fuer ein Thema, nicht fuer eine Entscheidung — also fuer "aufbereitet".

Tippfehler: Woerter ab vier Buchstaben werden unscharf verglichen, kuerzere
muessen exakt stimmen. Bei drei Buchstaben ist jeder zweite Tippfehler ein
anderes Wort — "ne" und "je" sind sich aehnlicher, als ihre Bedeutungen es
vertragen.
"""

import difflib

from absicht import extraktion
from absicht.erkenner import Treffer
from absicht.normalisierung import normalisieren, zerlegen

# Die ganze Nachricht ist genau ein Kurzbefehl.
SICHERHEIT_NACHRICHT_EXAKT = 0.97
# ... oder einem aehnlich genug. Wird zwischen der Schwelle fuer "direkt" und
# diesem Wert skaliert, damit ein knapper Abgleich nicht so viel wiegt wie
# ein sauberer.
SICHERHEIT_NACHRICHT_UNSCHARF_MAX = 0.96
# Die Nachricht beginnt mit einem Kurzbefehl, geht aber weiter.
SICHERHEIT_ANFANG = 0.88
SICHERHEIT_ANFANG_UNSCHARF = 0.78
# Eine Wortgruppe kommt vor: Grundwert fuer ein Wort, Zuschlag je weiterem.
SICHERHEIT_WENDUNG = 0.60
SICHERHEIT_WENDUNG_JE_WORT = 0.08
SICHERHEIT_WENDUNG_MAX = 0.85
# Mehrere verschiedene Wortgruppen derselben Absicht sprechen fuer sich.
ZUSCHLAG_MEHRERE_WENDUNGEN = 0.05
SICHERHEIT_WENDUNG_MEHRERE_MAX = 0.90


class WoerterbuchErkenner:
    """Gleicht eine Nachricht gegen die hinterlegten Wortlisten ab"""

    def __init__(self, absichten, verneinung, konfiguration):
        """
        Args:
            absichten (dict[str, Absicht]): siehe :mod:`absicht.absichten`
            verneinung (frozenset[str]): Verneinungswoerter dieser Sprache
            konfiguration (Konfiguration): Aehnlichkeitsgrenzen
        """
        self.absichten = absichten
        self.verneinung = verneinung
        self.konfiguration = konfiguration

        self._kurzbefehle = dict()
        self._kurzbefehle_ein_wort = dict()
        self._kurzbefehle_mehrwort = []
        self._wendungen = []
        self._vokabular = set()

        for name, definition in absichten.items():
            for kurzbefehl in definition.kurzbefehle:
                if not kurzbefehl:
                    continue
                self._kurzbefehle.setdefault(kurzbefehl, []).append(name)
                if " " in kurzbefehl:
                    self._kurzbefehle_mehrwort.append((kurzbefehl, name))
                else:
                    self._kurzbefehle_ein_wort.setdefault(
                        kurzbefehl, []).append(name)
            for wendung in definition.wendungen:
                if not wendung.woerter:
                    continue
                self._wendungen.append((name, wendung))
                self._vokabular.update(wendung.woerter)

        # Lange Kurzbefehle zuerst, damit "auf keinen fall" vor "auf" greift.
        self._kurzbefehle_mehrwort.sort(key=lambda paar: -len(paar[0]))
        self._alle_kurzbefehle = sorted(self._kurzbefehle)
        self._vokabular_nach_laenge = dict()
        for wort in self._vokabular:
            self._vokabular_nach_laenge.setdefault(len(wort), []).append(wort)
        self._kandidaten_zwischenspeicher = dict()

    def erkennen(self, text):
        """Bewertet einen Text gegen alle bekannten Absichten

        Args:
            text (str): Rohtext der Nachricht

        Returns:
            list[Treffer]: absteigend nach Sicherheit sortiert
        """
        nachricht = normalisieren(text)
        woerter = zerlegen(nachricht)
        if not woerter:
            return []

        bewertung = dict()
        self._nachricht_bewerten(nachricht, bewertung)
        self._anfang_bewerten(nachricht, woerter, bewertung)
        self._wendungen_bewerten(woerter, bewertung)

        verneint = self._verneinung_gefunden(woerter)
        treffer = []
        for name, (sicherheit, begruendung) in bewertung.items():
            definition = self.absichten[name]
            if verneint and definition.verneinung_schliesst_aus:
                # Die harte Grenze: keine Ablehnung darf je als Zustimmung
                # gelesen werden. Lieber gar kein Treffer als dieser.
                continue
            treffer.append(Treffer(
                absicht=name,
                sicherheit=round(min(sicherheit, 1.0), 4),
                begruendung=begruendung,
                extrakt=extraktion.auslesen(name, text, nachricht),
            ))

        treffer.sort(key=lambda t: (-t.sicherheit, t.absicht))
        return treffer

    def _nachricht_bewerten(self, nachricht, bewertung):
        """Die ganze Nachricht gegen die Kurzbefehle"""
        for name in self._kurzbefehle.get(nachricht, []):
            _merken(bewertung, name, SICHERHEIT_NACHRICHT_EXAKT,
                    'Nachricht ist genau der Kurzbefehl "%s"' % nachricht)
        if nachricht in self._kurzbefehle:
            return

        grenze = self.konfiguration.aehnlichkeit_nachricht
        aehnliche = difflib.get_close_matches(
            nachricht, self._alle_kurzbefehle, n=3, cutoff=grenze)
        for kurzbefehl in aehnliche:
            aehnlichkeit = difflib.SequenceMatcher(
                None, nachricht, kurzbefehl).ratio()
            sicherheit = _skalieren(
                aehnlichkeit, grenze,
                self.konfiguration.schwelle_direkt,
                SICHERHEIT_NACHRICHT_UNSCHARF_MAX)
            for name in self._kurzbefehle[kurzbefehl]:
                _merken(bewertung, name, sicherheit,
                        'Nachricht aehnelt dem Kurzbefehl "%s" (%.0f%%)'
                        % (kurzbefehl, aehnlichkeit * 100))

    def _anfang_bewerten(self, nachricht, woerter, bewertung):
        """Kurzbefehl am Anfang einer laengeren Nachricht"""
        if len(woerter) < 2:
            return

        for kurzbefehl, name in self._kurzbefehle_mehrwort:
            if nachricht.startswith(kurzbefehl + " "):
                _merken(bewertung, name, SICHERHEIT_ANFANG,
                        'Nachricht beginnt mit "%s"' % kurzbefehl)

        erstes = woerter[0]
        for name in self._kurzbefehle_ein_wort.get(erstes, []):
            _merken(bewertung, name, SICHERHEIT_ANFANG,
                    'Nachricht beginnt mit "%s"' % erstes)
        if erstes in self._kurzbefehle_ein_wort:
            return

        if len(erstes) < self.konfiguration.mindestlaenge_unscharf:
            return
        aehnliche = difflib.get_close_matches(
            erstes, sorted(self._kurzbefehle_ein_wort), n=1,
            cutoff=self.konfiguration.aehnlichkeit_wort)
        for kurzbefehl in aehnliche:
            for name in self._kurzbefehle_ein_wort[kurzbefehl]:
                _merken(bewertung, name, SICHERHEIT_ANFANG_UNSCHARF,
                        'Nachricht beginnt mit etwas wie "%s"' % kurzbefehl)

    def _wendungen_bewerten(self, woerter, bewertung):
        """Hinterlegte Wortgruppen im laufenden Text"""
        getroffen = set()
        for wort in woerter:
            getroffen.update(self._passende_woerter(wort))
        if not getroffen:
            return

        je_absicht = dict()
        for name, wendung in self._wendungen:
            if not set(wendung.woerter).issubset(getroffen):
                continue
            if wendung.sicherheit is not None:
                sicherheit = float(wendung.sicherheit)
            else:
                anzahl = len(set(wendung.woerter))
                sicherheit = min(
                    SICHERHEIT_WENDUNG
                    + SICHERHEIT_WENDUNG_JE_WORT * (anzahl - 1),
                    SICHERHEIT_WENDUNG_MAX)
            je_absicht.setdefault(name, []).append(
                (sicherheit, " ".join(wendung.woerter)))

        for name, gefunden in je_absicht.items():
            gefunden.sort(reverse=True)
            sicherheit, beste = gefunden[0]
            begruendung = 'Wortgruppe "%s" kommt vor' % beste
            if len(gefunden) > 1:
                sicherheit = min(sicherheit + ZUSCHLAG_MEHRERE_WENDUNGEN,
                                 SICHERHEIT_WENDUNG_MEHRERE_MAX)
                begruendung = '%d Wortgruppen kommen vor, darunter "%s"' % (
                    len(gefunden), beste)
            _merken(bewertung, name, sicherheit, begruendung)

    def _passende_woerter(self, wort):
        """Welche Vokabeln dieses Wort trifft — exakt oder mit Tippfehler"""
        if wort in self._vokabular:
            return (wort,)
        if len(wort) < self.konfiguration.mindestlaenge_unscharf:
            return ()
        kandidaten = self._kandidaten(len(wort))
        if not kandidaten:
            return ()
        return tuple(difflib.get_close_matches(
            wort, kandidaten, n=2,
            cutoff=self.konfiguration.aehnlichkeit_wort))

    def _kandidaten(self, laenge):
        """Vokabeln aehnlicher Laenge

        Zwei Woerter, deren Laengen um mehr als zwei Zeichen auseinander
        liegen, koennen die Aehnlichkeitsgrenze ohnehin nicht reissen. Das
        spart den grossen Teil der Vergleiche und haelt die Schicht unter
        einer Millisekunde.
        """
        gespeichert = self._kandidaten_zwischenspeicher.get(laenge)
        if gespeichert is None:
            gespeichert = sorted(
                wort
                for weite in range(laenge - 2, laenge + 3)
                for wort in self._vokabular_nach_laenge.get(weite, ()))
            self._kandidaten_zwischenspeicher[laenge] = gespeichert
        return gespeichert

    def _verneinung_gefunden(self, woerter):
        """Steht ein Verneinungswort in der Nachricht?

        Nur exakte Treffer: Verneinungen sind kurz, und ein unscharfer
        Abgleich wuerde hier in beide Richtungen irren — einmal zu viel, was
        blockiert, und einmal zu wenig, was gefaehrlich ist.
        """
        return any(wort in self.verneinung for wort in woerter)


def _merken(bewertung, name, sicherheit, begruendung):
    """Behaelt je Absicht den staerksten Grund"""
    vorher = bewertung.get(name)
    if vorher is None or sicherheit > vorher[0]:
        bewertung[name] = (sicherheit, begruendung)


def _skalieren(wert, von, auf_von, auf_bis):
    """Bildet ``wert`` aus [von, 1] linear auf [auf_von, auf_bis] ab"""
    if wert >= 1.0 or von >= 1.0:
        return auf_bis
    anteil = (wert - von) / (1.0 - von)
    return auf_von + anteil * (auf_bis - auf_von)
