"""Schritt 3: die Engine hinter derselben Schnittstelle.

Zwei Fragen werden hier beantwortet. Erstens: Bedient die portierte
NLU-Engine die Naht, ohne dass sich oberhalb davon etwas aendert? Zweitens,
und wichtiger: Gelten die Sicherheitsregeln auch dann noch? Eine Grenze, die
nur fuer das Woerterbuch gilt, ist keine Grenze.
"""

import random
import unittest

import absicht
from absicht.erkenner import Treffer
from absicht.erkenner.snips import SnipsErkenner, datensatz_bauen

try:
    import snips_nlu  # noqa: F401
    from snips_nlu.resources import MissingResource
    ENGINE_DA = True
except ImportError:
    ENGINE_DA = False


class TestSicherheitGiltFuerJedenErkenner(unittest.TestCase):
    """Die harte Grenze steht ueber der Naht, nicht darunter"""

    def test_fremder_erkenner_darf_keine_verneinung_zur_zustimmung_machen(self):
        class BehauptetZustimmung:
            """Ein Erkenner, der sich sicher ist — und sich irrt"""

            def erkennen(self, text):
                return [Treffer(absicht="zustimmung", sicherheit=1.0,
                                begruendung="Testerkenner")]

        schicht = absicht.Schicht.laden(erkenner=BehauptetZustimmung(),
                                        zufall=random.Random(0))
        for text in ("nein", "ja, aber nicht die erste", "auf keinen fall",
                     "kein Interesse"):
            ergebnis = schicht.pruefen(
                text, kontext={"ref": "0096", "letzte_frage": "freigabe"})
            self.assertNotEqual(
                "zustimmung", ergebnis["absicht"],
                "'%s' kam trotz Verneinung als Zustimmung durch" % text)
            aktion = ergebnis.get("aktion") or {}
            self.assertNotEqual("freigeben", aktion.get("art"))

    def test_streichung_steht_im_protokoll(self):
        class BehauptetZustimmung:
            def erkennen(self, text):
                return [Treffer(absicht="zustimmung", sicherheit=1.0,
                                begruendung="Testerkenner")]

        schicht = absicht.Schicht.laden(erkenner=BehauptetZustimmung(),
                                        zufall=random.Random(0))
        ergebnis = schicht.pruefen(
            "nein", kontext={"ref": "0096", "letzte_frage": "freigabe"},
            mit_protokoll=True)
        gruende = " ".join(ergebnis["protokoll"]["gruende"])
        self.assertIn("Verneinung", gruende)

    def test_fremder_erkenner_unterliegt_der_offenen_dialog_regel(self):
        class BehauptetZustimmung:
            def erkennen(self, text):
                return [Treffer(absicht="zustimmung", sicherheit=1.0,
                                begruendung="Testerkenner")]

        schicht = absicht.Schicht.laden(erkenner=BehauptetZustimmung(),
                                        zufall=random.Random(0))
        ergebnis = schicht.pruefen(
            "ja", kontext={"ref": "0096", "letzte_frage": "freigabe",
                           "offener_dialog": True})
        self.assertNotEqual(absicht.WEG_DIREKT, ergebnis["weg"])


class TestDatensatz(unittest.TestCase):
    """Aus den Absichtsdaten wird der Trainingsdatensatz"""

    def setUp(self):
        self.schicht = absicht.Schicht.laden(zufall=random.Random(0))

    def test_jede_absicht_bekommt_beispielsaetze(self):
        datensatz = datensatz_bauen(self.schicht.absichten)
        self.assertEqual("de", datensatz["language"])
        for name in self.schicht.absichten:
            self.assertIn(name, datensatz["intents"])
            saetze = datensatz["intents"][name]["utterances"]
            self.assertGreaterEqual(
                len(saetze), 4,
                "'%s' hat nur %d Beispielsaetze" % (name, len(saetze)))

    def test_beispielsaetze_liegen_in_der_erwarteten_groessenordnung(self):
        # Das Anforderungsdokument nennt 10-15 Beispielsaetze je Absicht als
        # vertretbaren Trainingsaufwand.
        datensatz = datensatz_bauen(self.schicht.absichten)
        anzahlen = [len(i["utterances"]) for i in datensatz["intents"].values()]
        self.assertGreaterEqual(sum(anzahlen) / len(anzahlen), 8)


@unittest.skipUnless(ENGINE_DA, "snips_nlu ist nicht installiert")
class TestSnipsErkenner(unittest.TestCase):
    """Die Engine bedient dieselbe Schnittstelle wie das Woerterbuch"""

    @classmethod
    def setUpClass(cls):
        vorlage = absicht.Schicht.laden()
        try:
            cls.erkenner = SnipsErkenner.trainieren(
                vorlage.absichten, random_state=42)
        except MissingResource as fehler:
            raise unittest.SkipTest(
                "Sprachressourcen fehlen: %s. 'snips-nlu download de'"
                % fehler)

    def test_erkennen_liefert_treffer(self):
        treffer = self.erkenner.erkennen("nein danke")
        self.assertTrue(treffer)
        self.assertIsInstance(treffer[0], Treffer)
        self.assertTrue(0.0 <= treffer[0].sicherheit <= 1.0)
        self.assertTrue(treffer[0].begruendung)

    def test_treffer_sind_absteigend_sortiert(self):
        treffer = self.erkenner.erkennen("nein danke")
        sicherheiten = [t.sicherheit for t in treffer]
        self.assertEqual(sorted(sicherheiten, reverse=True), sicherheiten)

    def test_leere_nachricht_gibt_keinen_treffer(self):
        for text in ("", "   ", None, "🙂"):
            self.assertEqual([], self.erkenner.erkennen(text))

    def test_engine_traegt_die_regelbasierten_angaben_weiter(self):
        treffer = self.erkenner.erkennen("Der letzte Absatz ist mir zu lang")
        passend = [t for t in treffer if t.absicht == "anschreiben_aendern"]
        self.assertTrue(passend)
        self.assertEqual("letzter Absatz", passend[0].extrakt.get("stelle"))

    def test_schicht_laeuft_mit_der_engine_unveraendert_weiter(self):
        schicht = absicht.Schicht.laden(erkenner=self.erkenner,
                                        zufall=random.Random(0))
        ergebnis = schicht.pruefen("nein danke", kontext={"ref": "0096"})
        self.assertIn(ergebnis["weg"],
                      (absicht.WEG_DIREKT, absicht.WEG_AUFBEREITET,
                       absicht.WEG_DURCHREICHEN))
        self.assertIn("sicherheit", ergebnis)

    def test_engine_unterliegt_derselben_harten_grenze(self):
        schicht = absicht.Schicht.laden(erkenner=self.erkenner,
                                        zufall=random.Random(0))
        for text in ("nein", "auf keinen fall", "ja, aber nicht die erste"):
            ergebnis = schicht.pruefen(
                text, kontext={"ref": "0096", "letzte_frage": "freigabe"})
            self.assertNotEqual("zustimmung", ergebnis["absicht"], text)


if __name__ == "__main__":
    unittest.main()
