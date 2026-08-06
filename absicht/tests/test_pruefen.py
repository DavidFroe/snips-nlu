"""Die Schnittstelle: drei Wege, ein Einstiegspunkt, kein Zustand."""

import random
import time
import unittest

import absicht
from absicht.erkenner import Treffer


class TestDreiWege(unittest.TestCase):

    def setUp(self):
        self.schicht = absicht.Schicht.laden(zufall=random.Random(0))

    def test_direkt_traegt_antwort_und_aktion(self):
        ergebnis = self.schicht.pruefen(
            "nein, lieber die andere zuerst", nutzer="david",
            kontext={"ref": "0096"})
        self.assertEqual(absicht.WEG_DIREKT, ergebnis["weg"])
        self.assertEqual("ablehnung", ergebnis["absicht"])
        self.assertGreaterEqual(ergebnis["sicherheit"], 0.80)
        self.assertTrue(ergebnis["antwort"])
        self.assertEqual("ablehnen", ergebnis["aktion"]["art"])
        self.assertEqual("0096", ergebnis["aktion"]["ref"])

    def test_aufbereitet_traegt_den_auftrag_ans_modell(self):
        ergebnis = self.schicht.pruefen(
            "Der letzte Absatz ist mir zu lang", kontext={"ref": "0096"})
        self.assertEqual(absicht.WEG_AUFBEREITET, ergebnis["weg"])
        self.assertEqual("anschreiben_aendern", ergebnis["absicht"])
        auftrag = ergebnis["llm_auftrag"]
        self.assertEqual("textaenderung", auftrag["zweck"])
        self.assertIn("anschreiben_aktuell", auftrag["prompt_bausteine"])
        self.assertIn("werkzeuge", auftrag["weglassen"])
        self.assertEqual("letzter Absatz", auftrag["extrakt"]["stelle"])
        self.assertEqual("kuerzer", auftrag["extrakt"]["wunsch"])

    def test_durchreichen_nennt_keine_absicht(self):
        ergebnis = self.schicht.pruefen(
            "solte ihre ausschreibung spezelle anforungen eahbebn")
        self.assertEqual(absicht.WEG_DURCHREICHEN, ergebnis["weg"])
        self.assertEqual("", ergebnis["absicht"])
        self.assertNotIn("antwort", ergebnis)
        self.assertNotIn("llm_auftrag", ergebnis)

    def test_leere_nachricht_wird_durchgereicht(self):
        for text in ("", "   ", None, "🙂", "???"):
            ergebnis = self.schicht.pruefen(text)
            self.assertEqual(absicht.WEG_DURCHREICHEN, ergebnis["weg"])


class TestBeispieleAusDemAnforderungsdokument(unittest.TestCase):
    """Die Beispiele, die im Anforderungsdokument woertlich stehen"""

    ERWARTET = [
        ("Nein", {"ref": "0096"}, "ablehnung"),
        ("Nein bitte die andere zuerst", {"ref": "0096"}, "ablehnung"),
        ("JO", {"ref": "0096", "letzte_frage": "freigabe"}, "zustimmung"),
        ("ja", {"ref": "0096", "letzte_frage": "freigabe"}, "zustimmung"),
        ("Ja, so passt das", {"ref": "0096", "letzte_frage": "freigabe"},
         "zustimmung"),
        ("Der letzte Absatz ist mir zu lang", {"ref": "0096"},
         "anschreiben_aendern"),
        ("Hallo?", {}, "lebenszeichen"),
        ("bist du da!?!?", {}, "lebenszeichen"),
        ("10 A nicht 10 KW", {"ref": "0096"}, "fachkorrektur"),
        ("kannst du 150 Ampere schreiben?", {"ref": "0096"}, "fachkorrektur"),
        ("ich muß ein Zeugnis löschen", {"ref": "0096"}, "unterlagen"),
        ("okay danke", {}, "dank"),
        ("Wieviele Bewerbungen sind zur Ansicht da?", {}, "statusfrage"),
    ]

    def setUp(self):
        self.schicht = absicht.Schicht.laden(zufall=random.Random(0))

    def test_alle_beispiele_werden_erkannt(self):
        fehler = []
        for text, kontext, erwartet in self.ERWARTET:
            ergebnis = self.schicht.pruefen(text, kontext=kontext)
            erkannt = ergebnis["absicht"] or "(durchgereicht)"
            if erkannt != erwartet:
                fehler.append("%r -> %s, erwartet %s"
                              % (text, erkannt, erwartet))
        self.assertEqual([], fehler, "\n".join(fehler))


class TestKeinZustand(unittest.TestCase):
    """Die Schicht merkt sich nichts zwischen zwei Aufrufen"""

    def test_gleiche_eingabe_gleicher_weg(self):
        schicht = absicht.Schicht.laden(zufall=random.Random(0))
        erster = schicht.pruefen("nein", kontext={"ref": "0096"})
        for _ in range(20):
            weiterer = schicht.pruefen("nein", kontext={"ref": "0096"})
            self.assertEqual(erster["weg"], weiterer["weg"])
            self.assertEqual(erster["absicht"], weiterer["absicht"])
            self.assertEqual(erster["sicherheit"], weiterer["sicherheit"])

    def test_vorherige_nachricht_beeinflusst_die_naechste_nicht(self):
        schicht = absicht.Schicht.laden(zufall=random.Random(0))
        allein = schicht.pruefen("danke")
        schicht.pruefen("ja", kontext={"ref": "1", "letzte_frage": "freigabe"})
        schicht.pruefen("nein", kontext={"ref": "2"})
        danach = schicht.pruefen("danke")
        self.assertEqual(allein["absicht"], danach["absicht"])
        self.assertEqual(allein["sicherheit"], danach["sicherheit"])


class TestAntwortbibliothek(unittest.TestCase):

    def test_mehrere_antworten_werden_abgewechselt(self):
        schicht = absicht.Schicht.laden(zufall=random.Random(12))
        gesehen = {
            schicht.pruefen("danke")["antwort"] for _ in range(60)}
        self.assertGreater(
            len(gesehen), 1,
            "Immer derselbe Satz — nach dem dritten Mal ist das eine Maschine")

    def test_antwort_mit_unfuellbarem_platzhalter_wird_uebersprungen(self):
        schicht = absicht.Schicht.laden(zufall=random.Random(0))
        # Beide Antworten zu "unterlagen" brauchen {portal}; fehlt es, darf
        # keine halbe Antwort rausgehen.
        ohne = schicht.pruefen("ich muß ein Zeugnis löschen",
                               kontext={"ref": "0096"})
        self.assertNotEqual(absicht.WEG_DIREKT, ohne["weg"])

        mit = schicht.pruefen(
            "ich muß ein Zeugnis löschen",
            kontext={"ref": "0096", "portal": "https://portal.example"})
        self.assertEqual(absicht.WEG_DIREKT, mit["weg"])
        self.assertIn("https://portal.example/bewerbung/0096/unterlagen",
                      mit["antwort"])


class TestErkennerAustauschbar(unittest.TestCase):
    """Die Naht, um die es im Auftrag geht"""

    def test_fremder_erkenner_bedient_dieselbe_schnittstelle(self):
        class ImmerAblehnung:
            def erkennen(self, text):
                return [Treffer(absicht="ablehnung", sicherheit=0.99,
                                begruendung="Testerkenner")]

        schicht = absicht.Schicht.laden(erkenner=ImmerAblehnung(),
                                        zufall=random.Random(0))
        ergebnis = schicht.pruefen("was auch immer", kontext={"ref": "0096"})
        self.assertEqual(absicht.WEG_DIREKT, ergebnis["weg"])
        self.assertEqual("ablehnung", ergebnis["absicht"])

    def test_unbekannte_absicht_eines_erkenners_wird_verworfen(self):
        class Fantasie:
            def erkennen(self, text):
                return [Treffer(absicht="gibt_es_nicht", sicherheit=1.0)]

        schicht = absicht.Schicht.laden(erkenner=Fantasie(),
                                        zufall=random.Random(0))
        ergebnis = schicht.pruefen("egal", kontext={"ref": "0096"})
        self.assertEqual(absicht.WEG_DURCHREICHEN, ergebnis["weg"])


class TestProtokoll(unittest.TestCase):
    """Ohne nachvollziehbares Protokoll ist der Schattenbetrieb wertlos"""

    def test_protokoll_traegt_text_absicht_sicherheit_weg_und_grund(self):
        schicht = absicht.Schicht.laden(zufall=random.Random(0))
        ergebnis = schicht.pruefen(
            "nein", nutzer="david", kontext={"ref": "0096"},
            mit_protokoll=True)
        satz = ergebnis["protokoll"]
        self.assertEqual("nein", satz["text"])
        self.assertEqual("david", satz["nutzer"])
        self.assertEqual("ablehnung", satz["absicht"])
        self.assertEqual(absicht.WEG_DIREKT, satz["weg"])
        self.assertTrue(satz["gruende"])
        self.assertEqual({"ref": "0096"}, satz["kontext"])
        self.assertTrue(satz["zeit"])

    def test_protokoll_begruendet_auch_eine_unterdrueckte_entscheidung(self):
        schicht = absicht.Schicht.laden(zufall=random.Random(0))
        ergebnis = schicht.pruefen(
            "ja", kontext={"ref": "0096"}, mit_protokoll=True)
        gruende = " ".join(ergebnis["protokoll"]["gruende"])
        self.assertIn("Frage", gruende)

    def test_ohne_anforderung_kein_protokoll_im_ergebnis(self):
        schicht = absicht.Schicht.laden(zufall=random.Random(0))
        ergebnis = schicht.pruefen("nein", kontext={"ref": "0096"})
        self.assertNotIn("protokoll", ergebnis)


class TestAntwortzeit(unittest.TestCase):
    """Unter 10 ms — darueber lohnt das Umgehen des Modells nicht"""

    def test_pruefen_bleibt_unter_zehn_millisekunden(self):
        schicht = absicht.Schicht.laden(zufall=random.Random(0))
        nachrichten = [
            "nein",
            "Ja, so passt das",
            "Der letzte Absatz ist mir zu lang und zu förmlich",
            "solte ihre ausschreibung spezelle anforungen eahbebn",
            "ich muß ein Zeugnis löschen und den Lebenslauf tauschen",
        ]
        kontext = {"ref": "0096", "letzte_frage": "freigabe"}
        for text in nachrichten:
            schicht.pruefen(text, kontext=kontext)

        beginn = time.perf_counter()
        durchlaeufe = 200
        for _ in range(durchlaeufe):
            for text in nachrichten:
                schicht.pruefen(text, kontext=kontext)
        je_aufruf = (time.perf_counter() - beginn) / (
            durchlaeufe * len(nachrichten))
        self.assertLess(
            je_aufruf, 0.010,
            "%.2f ms je Aufruf — das Ziel sind 10 ms" % (je_aufruf * 1000))


if __name__ == "__main__":
    unittest.main()
