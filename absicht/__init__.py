"""Die Absichtsschicht: entscheiden, was ohne Sprachmodell geht.

Heute geht jede eingehende Bewerbernachricht ungefiltert an ein Sprachmodell —
rund 11.000 Zeichen Grundlast, etwa 2.800 Token, Antwortzeiten bis 107
Sekunden. Auch dann, wenn ein Bewerber "Nein" schreibt. Vier Zeichen.

Diese Schicht steht davor und entscheidet in unter 10 ms zwischen drei Wegen:

>>> import absicht
>>> ergebnis = absicht.pruefen("nein danke", kontext={"ref": "0096"})
>>> ergebnis["weg"], ergebnis["absicht"]
('direkt', 'ablehnung')

Sie merkt sich nichts zwischen zwei Aufrufen, sie redet mit niemandem, und sie
laeuft als Bibliothek im Bot mit — kein zwoelfter Container. Der Zustand liegt
in der Datenbank des Aufrufers und hat dort genau einen Besitzer.

Was darunter erkennt, ist austauschbar: heute ein Woerterbuch mit ``difflib``,
morgen vielleicht die portierte NLU-Engine. Die Naht dafuer ist
:mod:`absicht.erkenner`; oberhalb davon kennt niemand die Engine.
"""

from absicht import absichten as _absichten
from absicht import protokoll as _protokoll
from absicht.antworten import Antwortbibliothek
from absicht.entscheidung import (
    WEG_AUFBEREITET, WEG_DIREKT, WEG_DURCHREICHEN, entscheiden,
    verneinung_sperrt, zu_lang)
from absicht.erkenner.woerterbuch import WoerterbuchErkenner
from absicht.konfiguration import Konfiguration

__all__ = ["pruefen", "Schicht", "Konfiguration", "laden",
           "WEG_DIREKT", "WEG_AUFBEREITET", "WEG_DURCHREICHEN"]

__version__ = "0.1.0"


class Schicht:
    """Die Absichtsschicht in Objektform

    Fuer den Regelfall genuegt die Modulfunktion :func:`pruefen`. Diese Klasse
    braucht, wer mehrere Sprachen nebeneinander betreibt, eigene Schwellen
    setzt oder den Erkenner austauscht.
    """

    def __init__(self, erkenner, absichten, verneinung, antworten,
                 konfiguration):
        self.erkenner = erkenner
        self.absichten = absichten
        self.verneinung = verneinung
        self.antworten = antworten
        self.konfiguration = konfiguration

    @classmethod
    def laden(cls, konfiguration=None, erkenner=None, zufall=None):
        """Baut eine Schicht aus den Datendateien

        Args:
            konfiguration (Konfiguration, optional): Schwellen und Sprache
            erkenner (optional): eigener Erkenner; ohne Angabe das Woerterbuch
            zufall (random.Random, optional): fuer vorhersagbare Antwortwahl
                in Tests
        """
        konfiguration = konfiguration or Konfiguration()
        definitionen, verneinung = _absichten.laden(
            konfiguration.absichten_datei())
        antworten = Antwortbibliothek.laden(
            konfiguration.antworten_datei(), zufall=zufall)
        if erkenner is None:
            erkenner = WoerterbuchErkenner(definitionen, konfiguration)
        return cls(erkenner, definitionen, verneinung, antworten,
                   konfiguration)

    def pruefen(self, text, nutzer=None, kontext=None, mit_protokoll=False):
        """Siehe :func:`absicht.pruefen`"""
        erkannt = [
            t for t in self.erkenner.erkennen(text or "")
            if t.absicht in self.absichten]
        # Die harten Grenzen werden hier gezogen, nicht im Erkenner: sie
        # muessen gelten, egal wer unter der Naht arbeitet.
        treffer, gestrichen = verneinung_sperrt(
            erkannt, text, self.absichten, self.verneinung)
        treffer, zu_lang_gestrichen = zu_lang(treffer, text, self.absichten)
        gestrichen = gestrichen + zu_lang_gestrichen
        ergebnis, spuren = entscheiden(
            treffer, kontext, nutzer, self.absichten, self.antworten,
            self.konfiguration)

        satz = _protokoll.satz(
            text, nutzer, kontext, ergebnis, erkannt,
            gestrichen + spuren["gruende"])
        _protokoll.schreiben(satz)
        if mit_protokoll:
            ergebnis = dict(ergebnis)
            ergebnis["protokoll"] = satz
        return ergebnis


_schicht = None


def laden(konfiguration=None, erkenner=None, zufall=None):
    """Setzt die Schicht neu auf, die :func:`pruefen` benutzt

    Der Aufrufer ruft das einmal beim Start, wenn er von den Voreinstellungen
    abweichen will. Ohne Aufruf baut sich die Schicht beim ersten
    :func:`pruefen` selbst.

    Returns:
        Schicht: die neu gesetzte Schicht
    """
    global _schicht
    _schicht = Schicht.laden(
        konfiguration=konfiguration, erkenner=erkenner, zufall=zufall)
    return _schicht


def pruefen(text, nutzer=None, kontext=None, mit_protokoll=False):
    """Entscheidet, wie eine eingehende Nachricht behandelt wird

    Args:
        text (str): die Nachricht, unveraendert so wie sie ankam
        nutzer (str, optional): wer schreibt. Steht Antworten als Platzhalter
            ``{nutzer}`` zur Verfuegung.
        kontext (dict, optional): was der Aufrufer weiss. Erwartet werden,
            alle einzeln optional:

            ``ref``
                worueber gerade gesprochen wird, etwa ``"0096"``
            ``letzte_frage``
                was *wir* zuletzt gefragt haben, etwa ``"freigabe"``. Fehlt
                sie, ist ein "ja" bedeutungslos.
            ``offener_dialog``
                laeuft gerade ein Freitextgespraech? Dann gibt die Schicht
                fuer Absichten mit Aktion niemals ``direkt`` zurueck.
            ``zustand``, ``kanal``
                werden durchgereicht und stehen Antworten als Platzhalter zur
                Verfuegung
        mit_protokoll (bool): legt den Protokollsatz unter ``"protokoll"``
            ins Ergebnis. Fuer den Schattenbetrieb, in dem mitgeschrieben
            wird, was die Schicht entschieden haette.

    Returns:
        dict: einer von drei Faellen —

        ``weg="direkt"``
            mit ``absicht``, ``sicherheit``, ``antwort`` und ``aktion``.
            Wir antworten selbst.
        ``weg="aufbereitet"``
            mit ``absicht``, ``sicherheit`` und ``llm_auftrag``. Das Modell
            wird gebraucht, aber der Prompt kann klein bleiben.
        ``weg="durchreichen"``
            mit leerer ``absicht``. Voller Kontext ans Modell.
    """
    if _schicht is None:
        laden()
    return _schicht.pruefen(
        text, nutzer=nutzer, kontext=kontext, mit_protokoll=mit_protokoll)
