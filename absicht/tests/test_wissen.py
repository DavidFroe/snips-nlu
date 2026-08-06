"""Der Wissensspeicher — vor allem die Trennung zwischen Bewerbern.

Die Trennung ist keine Ordnungsfrage: Landet ein Satz aus Davids
Lebenslauf in Tonis Anschreiben, steht in einem Dokument an einen
Arbeitgeber eine Behauptung ueber einen Menschen, die nicht stimmt.
Deshalb steht sie hier an erster Stelle.
"""

import pytest

from absicht.wissen import OhneEinbetter, Speicher
from absicht.wissen.einbetten import aehnlichkeit


class FesterEinbetter(OhneEinbetter):
    """Gibt vorbereitete Vektoren zurueck — fuer Tests ohne Netz"""

    def __init__(self, tabelle):
        self.tabelle = tabelle

    def einbetten(self, text):
        return self.tabelle.get(text)


# ── Die Trennung ────────────────────────────────────────────────────────

def test_ohne_nutzer_gibt_es_keinen_speicher(tmp_path):
    with pytest.raises(ValueError):
        Speicher("", tmp_path / "x.json")
    with pytest.raises(ValueError):
        Speicher("   ", tmp_path / "x.json")


def test_fremde_datei_wird_abgewiesen(tmp_path):
    """Eine verschobene Datei darf nicht als Speicher eines anderen gelten"""
    davids = Speicher("david", tmp_path / "wissen.json")
    davids.merken("Ich habe FPGAs mit Xilinx programmiert", quelle="chat")
    davids.sichern()

    # Dieselbe Datei, anderer Nutzer: muss auffliegen.
    with pytest.raises(ValueError) as fehler:
        Speicher("toni", tmp_path / "wissen.json")
    assert "david" in str(fehler.value)


def test_zwei_bewerber_sehen_einander_nicht(tmp_path):
    davids = Speicher("david", tmp_path / "david.json")
    davids.merken("Ich habe Weidezaungeraete entwickelt")
    davids.sichern()

    tonis = Speicher("toni", tmp_path / "toni.json")
    tonis.merken("Ich fahre Gabelstapler")
    tonis.sichern()

    assert davids.suchen("Weidezaun")
    assert not tonis.suchen("Weidezaun")
    assert tonis.suchen("Gabelstapler")
    assert not davids.suchen("Gabelstapler")


# ── Aufnehmen ───────────────────────────────────────────────────────────

def test_leeres_wird_nicht_aufgenommen(tmp_path):
    s = Speicher("david", tmp_path / "d.json")
    assert s.merken("") is None
    assert s.merken("   ") is None
    assert len(s) == 0


def test_doppeltes_wird_uebersprungen(tmp_path):
    """Der Bewerber wiederholt sich — dreimal derselbe Satz hilft nicht"""
    s = Speicher("david", tmp_path / "d.json")
    assert s.merken("Ich habe FPGAs programmiert") is not None
    assert s.merken("ich habe fpgas programmiert!") is None
    assert len(s) == 1


# ── Suchen ──────────────────────────────────────────────────────────────

def test_volltext_findet_ueber_gemeinsame_woerter(tmp_path):
    s = Speicher("david", tmp_path / "d.json")
    s.merken("Ich habe Weidezaungeraete mit Hochspannungsgeneratoren gebaut")
    s.merken("Bei KNDS war ich fuer Bordnetzarchitektur zustaendig")

    treffer = s.suchen("Hochspannungsgeneratoren")
    assert treffer
    assert "Weidezaun" in treffer[0][0].text


def test_kurze_woerter_stiften_keine_treffer(tmp_path):
    """"mit", "der", "und" duerfen keine Aehnlichkeit begruenden"""
    s = Speicher("david", tmp_path / "d.json")
    s.merken("Ich habe mit der Software und dem Team gearbeitet")
    assert not s.suchen("mit der und")


def test_einbettung_geht_vor_volltext(tmp_path):
    """Inhaltlich Verwandtes ohne gemeinsame Woerter"""
    frage = "Erfahrung mit programmierbarer Logik"
    treffer_text = "FPGA-Entwicklung mit Xilinx und Lattice"
    daneben = "Ich habe im Vertrieb gearbeitet"
    einbetter = FesterEinbetter({
        frage: [1.0, 0.0, 0.0],
        treffer_text: [0.9, 0.1, 0.0],
        daneben: [0.0, 0.0, 1.0],
    })
    s = Speicher("david", tmp_path / "d.json", einbetter)
    s.merken(treffer_text)
    s.merken(daneben)

    treffer = s.suchen(frage)
    assert treffer
    assert treffer[0][0].text == treffer_text


def test_ohne_einbetter_faellt_es_auf_volltext_zurueck(tmp_path):
    """Faellt der Dienst aus, findet der Speicher weiter — nur weniger"""
    s = Speicher("david", tmp_path / "d.json", OhneEinbetter())
    s.merken("FPGA-Entwicklung mit Xilinx und Lattice")
    assert s.suchen("Erfahrung mit programmierbarer Logik") == []
    assert s.suchen("Xilinx Entwicklung")


def test_hoechstens_begrenzt(tmp_path):
    """Der Zweck ist ein kleinerer Prompt — nicht zwanzig Absaetze"""
    s = Speicher("david", tmp_path / "d.json")
    for n in range(10):
        s.merken("Projekt Nummer %d mit Mikrocontrollern und Sensorik" % n)
    assert len(s.suchen("Mikrocontrollern Sensorik", hoechstens=3)) == 3


# ── Ablage ──────────────────────────────────────────────────────────────

def test_gesichertes_kommt_zurueck(tmp_path):
    s = Speicher("david", tmp_path / "d.json")
    s.merken("Ich habe FPGAs programmiert", quelle="chat", ref="0096")
    s.sichern()

    wieder = Speicher("david", tmp_path / "d.json")
    assert len(wieder) == 1
    assert wieder.stuecke[0].quelle == "chat"
    assert wieder.stuecke[0].ref == "0096"


def test_fehlende_datei_ist_kein_fehler(tmp_path):
    """Ein neuer Bewerber hat noch keinen Speicher — das ist der Normalfall"""
    s = Speicher("neuling", tmp_path / "gibtsnicht.json")
    assert len(s) == 0


# ── Aehnlichkeit ────────────────────────────────────────────────────────

def test_aehnlichkeit_haelt_die_grenzen_ein():
    assert aehnlichkeit([1, 0], [1, 0]) == pytest.approx(1.0)
    assert aehnlichkeit([1, 0], [0, 1]) == pytest.approx(0.0)
    assert aehnlichkeit([1, 0], [-1, 0]) == pytest.approx(-1.0)


def test_aehnlichkeit_vertraegt_unsinn():
    """Leere und ungleich lange Vektoren duerfen nicht werfen"""
    assert aehnlichkeit([], [1, 2]) == 0.0
    assert aehnlichkeit([1, 2], [1, 2, 3]) == 0.0
    assert aehnlichkeit([0, 0], [1, 1]) == 0.0
