"""Die Grenzen, die nicht verhandelbar sind.

Bei 34 Ablehnungen in 253 Nachrichten ist ein falsch gelesenes Ja kein
theoretisches Risiko. Geht eine Bewerbung raus, die niemand freigegeben hat,
ist das der teuerste Fehler, den dieses System machen kann.

Fallen diese Tests, wird nichts ausgeliefert.
"""

import random
import unittest

import absicht
from absicht.konfiguration import Konfiguration


class TestKeineAblehnungAlsZustimmung(unittest.TestCase):
    """Keine einzige Ablehnung darf als Zustimmung gelesen werden"""

    ABLEHNUNGEN = [
        "nein",
        "Nein",
        "NEIN",
        "nein!",
        "neee",
        "nee",
        "ne",
        "nö",
        "Nein danke",
        "nein, lieber die andere zuerst",
        "Nein bitte die andere zuerst",
        "auf keinen fall",
        "lieber nicht",
        "bloß nicht",
        "will ich nicht",
        "das nicht abschicken",
        "die nicht nehmen",
        "nein, so nicht",
        "ja, aber nicht die erste",
        "ja nein doch nicht",
        "ne lass mal",
        "nein 🙂",
        "nein...",
        "NEIN!!!",
        "nein nein nein",
        "eher nicht",
        "keinesfalls",
        "niemals",
        "nichts davon",
        "kein Interesse",
    ]

    def setUp(self):
        self.schicht = absicht.Schicht.laden(zufall=random.Random(0))

    def test_keine_ablehnung_wird_zustimmung(self):
        for text in self.ABLEHNUNGEN:
            for kontext in (
                    {},
                    {"ref": "0096"},
                    {"ref": "0096", "letzte_frage": "freigabe"},
                    {"ref": "0096", "letzte_frage": "freigabe",
                     "offener_dialog": True},
            ):
                ergebnis = self.schicht.pruefen(text, kontext=kontext)
                self.assertNotEqual(
                    "zustimmung", ergebnis["absicht"],
                    "'%s' wurde bei Kontext %s als Zustimmung gelesen"
                    % (text, kontext))

    def test_keine_ablehnung_loest_eine_freigabe_aus(self):
        for text in self.ABLEHNUNGEN:
            ergebnis = self.schicht.pruefen(
                text, kontext={"ref": "0096", "letzte_frage": "freigabe"})
            aktion = ergebnis.get("aktion") or {}
            self.assertNotEqual(
                "freigeben", aktion.get("art"),
                "'%s' hat eine Freigabe ausgeloest" % text)


class TestOffenerDialog(unittest.TestCase):
    """Steht ein Freitextgespraech, wird nichts direkt entschieden"""

    def setUp(self):
        self.schicht = absicht.Schicht.laden(zufall=random.Random(0))

    def test_zustimmung_im_offenen_dialog_niemals_direkt(self):
        ergebnis = self.schicht.pruefen(
            "Ja",
            kontext={"ref": "0096", "letzte_frage": "freigabe",
                     "offener_dialog": True})
        self.assertNotEqual(absicht.WEG_DIREKT, ergebnis["weg"])

    def test_ablehnung_im_offenen_dialog_niemals_direkt(self):
        ergebnis = self.schicht.pruefen(
            "nein", kontext={"ref": "0096", "offener_dialog": True})
        self.assertNotEqual(absicht.WEG_DIREKT, ergebnis["weg"])

    def test_absicht_ohne_aktion_bleibt_im_offenen_dialog_erlaubt(self):
        # "danke" traegt keine Aktion; darauf zu antworten kann nichts
        # ausloesen, also bleibt der kurze Weg offen.
        ergebnis = self.schicht.pruefen(
            "danke", kontext={"ref": "0096", "offener_dialog": True})
        self.assertEqual(absicht.WEG_DIREKT, ergebnis["weg"])


class TestOhneFrageKeineZustimmung(unittest.TestCase):
    """Ohne letzte_frage ist ein "ja" bedeutungslos"""

    def setUp(self):
        self.schicht = absicht.Schicht.laden(zufall=random.Random(0))

    def test_ja_ohne_letzte_frage_wird_durchgereicht(self):
        for text in ("ja", "JO", "klar", "passt so", "einverstanden"):
            ergebnis = self.schicht.pruefen(text, kontext={"ref": "0096"})
            self.assertEqual(
                absicht.WEG_DURCHREICHEN, ergebnis["weg"],
                "'%s' ohne letzte_frage haette durchgereicht werden muessen"
                % text)
            self.assertEqual("", ergebnis["absicht"])

    def test_ja_mit_letzter_frage_wird_zustimmung(self):
        ergebnis = self.schicht.pruefen(
            "ja", kontext={"ref": "0096", "letzte_frage": "freigabe"})
        self.assertEqual("zustimmung", ergebnis["absicht"])


class TestFolgenreicheAbsichten(unittest.TestCase):
    """Wer etwas verschickt, soll sich sicher sein: 0,95 statt 0,80"""

    def test_zustimmung_unter_der_hoeheren_schwelle_geht_nicht_direkt(self):
        # Eine Konfiguration, in der die uebliche Schwelle laengst erreicht
        # waere, die hoehere aber nicht.
        streng = Konfiguration(schwelle_direkt=0.50,
                               schwelle_folgenreich=0.99)
        schicht = absicht.Schicht.laden(konfiguration=streng,
                                        zufall=random.Random(0))
        ergebnis = schicht.pruefen(
            "kannst abschicken",
            kontext={"ref": "0096", "letzte_frage": "freigabe"})
        self.assertNotEqual(absicht.WEG_DIREKT, ergebnis["weg"])

    def test_ablehnung_bleibt_bei_der_gewoehnlichen_schwelle(self):
        streng = Konfiguration(schwelle_direkt=0.50,
                               schwelle_folgenreich=0.99)
        schicht = absicht.Schicht.laden(konfiguration=streng,
                                        zufall=random.Random(0))
        ergebnis = schicht.pruefen("nein", kontext={"ref": "0096"})
        self.assertEqual(absicht.WEG_DIREKT, ergebnis["weg"])


class TestBezug(unittest.TestCase):
    """Ohne Bezug ist eine Aktion nicht anwendbar"""

    def setUp(self):
        self.schicht = absicht.Schicht.laden(zufall=random.Random(0))

    def test_ablehnung_ohne_ref_geht_nicht_direkt(self):
        ergebnis = self.schicht.pruefen("nein", kontext={})
        self.assertNotEqual(absicht.WEG_DIREKT, ergebnis["weg"])

    def test_ablehnung_mit_ref_nennt_die_ref_in_der_aktion(self):
        ergebnis = self.schicht.pruefen("nein", kontext={"ref": "0096"})
        self.assertEqual({"art": "ablehnen", "ref": "0096"},
                         ergebnis["aktion"])


if __name__ == "__main__":
    unittest.main()
