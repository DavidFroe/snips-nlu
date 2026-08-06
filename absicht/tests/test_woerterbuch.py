"""Normalisierung, Tippfehlertoleranz und das Auslesen von Angaben."""

import random
import unittest

import absicht
from absicht.extraktion import auslesen
from absicht.normalisierung import normalisieren, zerlegen


class TestNormalisierung(unittest.TestCase):

    def test_umlaute_und_scharfes_s_werden_aufgeloest(self):
        self.assertEqual("ich muss ein zeugnis loeschen",
                         normalisieren("Ich muß ein Zeugnis löschen"))
        self.assertEqual("aendern", normalisieren("Ändern"))

    def test_satzzeichen_und_emojis_fallen_weg(self):
        self.assertEqual("hallo", normalisieren("Hallo?!?"))
        self.assertEqual("nein", normalisieren("nein 🙂"))
        self.assertEqual("bist du da", normalisieren("bist du da!?!?"))

    def test_gedehnte_buchstaben_werden_gekuerzt(self):
        self.assertEqual("nee", normalisieren("neeeeee"))
        self.assertEqual("jaa", normalisieren("jaaaaaa"))

    def test_ziffern_bleiben_erhalten(self):
        # "10 A nicht 10 KW" haengt daran.
        self.assertEqual("10 a nicht 10 kw", normalisieren("10 A nicht 10 KW"))

    def test_leere_eingaben(self):
        self.assertEqual("", normalisieren(""))
        self.assertEqual("", normalisieren(None))
        self.assertEqual("", normalisieren("   "))
        self.assertEqual([], zerlegen(""))


class TestTippfehler(unittest.TestCase):
    """Die Nachrichten sind umgangssprachlich und voller Tippfehler"""

    def setUp(self):
        self.schicht = absicht.Schicht.laden(zufall=random.Random(0))

    def test_verschriebene_kurzbefehle_werden_erkannt(self):
        for text, erwartet in (("danek", "dank"),
                               ("hallp", "lebenszeichen"),
                               ("dankee", "dank"),
                               ("hallooo", "lebenszeichen"),
                               ("zuegnis loeschen", "unterlagen")):
            ergebnis = self.schicht.pruefen(
                text, kontext={"ref": "0096"}, mit_protokoll=True)
            kandidaten = ergebnis["protokoll"]["kandidaten"]
            self.assertTrue(kandidaten, "'%s' wurde gar nicht zugeordnet"
                            % text)
            self.assertEqual(erwartet, kandidaten[0]["absicht"], text)

    def test_vertauschte_buchstaben_in_kurzen_woertern_gehen_durch(self):
        """Die Grenze der Tippfehlertoleranz, damit sie niemanden ueberrascht

        Bei vier Buchstaben liegt eine Vertauschung ("nien" statt "nein") bei
        75 % Aehnlichkeit — genau dort, wo auch "kein" und "jein" liegen.
        Wer die Grenze so weit senkt, liest irgendwann ein "jein" als "nein".
        Diese Nachrichten gehen deshalb durch, und das ist die sichere Seite:
        Sie kosten Token, aber sie loesen nichts aus.
        """
        ergebnis = self.schicht.pruefen("nien", kontext={"ref": "0096"})
        self.assertEqual(absicht.WEG_DURCHREICHEN, ergebnis["weg"])

    def test_kurze_woerter_werden_nicht_unscharf_verglichen(self):
        # "je" darf nicht auf "ja" fallen: bei zwei Buchstaben ist jeder
        # Tippfehler ein anderes Wort.
        ergebnis = self.schicht.pruefen(
            "je", kontext={"ref": "0096", "letzte_frage": "freigabe"})
        self.assertNotEqual("zustimmung", ergebnis["absicht"])


class TestExtraktion(unittest.TestCase):

    def test_stelle_und_wunsch_im_anschreiben(self):
        self.assertEqual(
            {"stelle": "letzter Absatz", "wunsch": "kuerzer"},
            auslesen("anschreiben_aendern",
                     "Der letzte Absatz ist mir zu lang",
                     normalisieren("Der letzte Absatz ist mir zu lang")))
        self.assertEqual(
            "Einleitung",
            auslesen("anschreiben_aendern", "Die Einleitung bitte förmlicher",
                     normalisieren("Die Einleitung bitte förmlicher"))
            ["stelle"])

    def test_richtig_und_falsch_bei_einer_fachkorrektur(self):
        self.assertEqual(
            {"richtig": "10 A", "falsch": "10 KW"},
            auslesen("fachkorrektur", "10 A nicht 10 KW", "10 a nicht 10 kw"))
        self.assertEqual(
            {"richtig": "150 Ampere", "falsch": "15"},
            auslesen("fachkorrektur", "150 Ampere statt 15",
                     "150 ampere statt 15"))

    def test_ohne_erkennbare_angabe_bleibt_das_extrakt_leer(self):
        # Was nicht sicher erkannt wird, fehlt lieber, als geraten zu werden.
        self.assertEqual(
            dict(),
            auslesen("anschreiben_aendern", "mach mal was dran",
                     normalisieren("mach mal was dran")))
        self.assertEqual(dict(), auslesen("dank", "danke", "danke"))


if __name__ == "__main__":
    unittest.main()
