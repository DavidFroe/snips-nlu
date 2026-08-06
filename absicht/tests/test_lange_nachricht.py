"""Die Laengengrenze — dass sie ueber der Naht liegt und nicht darunter.

Der Anlass steht in den Verlaeufen: „Hallo, bekomme ich eine Antwort im
Portal?" wurde als Lebenszeichen gelesen und mit „Ja, ich bin da. Was
brauchst du?" beantwortet. Also genau das Ausweichen, gegen das die
Schicht gebaut ist — auf eine echte Frage.
"""

import absicht
from absicht.entscheidung import zu_lang
from absicht.erkenner import Treffer


def test_kurzes_hallo_ist_ein_lebenszeichen():
    e = absicht.pruefen("hallo?", kontext={"ref": "0096"})
    assert e["weg"] == "direkt"
    assert e["absicht"] == "lebenszeichen"


def test_lange_frage_mit_hallo_geht_ans_modell():
    e = absicht.pruefen("Hallo, bekomme ich eine Antwort im Portal?",
                        kontext={"ref": "0096"})
    assert e["absicht"] != "lebenszeichen"


def test_grenze_gilt_fuer_jeden_erkenner():
    """Auch fuer einen, der die Absicht einfach behauptet.

    Das ist der Sinn der Naht: Ein ausgetauschter Erkenner darf die Regel
    nicht umgehen koennen.
    """
    schicht = absicht.laden()
    behauptet = [Treffer(absicht="lebenszeichen", sicherheit=1.0,
                         begruendung="behauptet")]
    verblieben, gestrichen = zu_lang(
        behauptet,
        "Hallo, ich wollte fragen ob die Bewerbung schon raus ist bei euch",
        schicht.absichten)
    assert verblieben == []
    assert gestrichen
