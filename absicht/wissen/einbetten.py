"""Text zu Vektor — über den Hausproxy, mit Rückfall.

Zwei Umsetzungen, und die zweite ist kein Notbehelf:

:class:`ProxyEinbetter`
    Ruft ``POST /v1/embeddings`` am QuiteQue-Proxy. Das Modell läuft
    woanders; auf dieser Maschine kostet es kein Byte Arbeitsspeicher.
:class:`OhneEinbetter`
    Gibt für jeden Text ``None`` zurück. Der Speicher fällt dann auf
    Volltextsuche zurück.

**Warum der Rückfall keine Verlegenheitslösung ist:** Der
Embedding-Endpunkt steht in `QUITEQUE_INTERFACE.md` nicht. Er existiert
und antwortet, ist aber undokumentiert — QuiteQue reicht ihn an Ollama
durch, erkennbar an der Fehlermeldung ``model not found, try pulling it
first``. Was nicht im Vertrag steht, kann ohne Ankündigung verschwinden.
Ein Wissensspeicher, der dann gar nichts mehr findet, ist schlechter als
einer, der Stichworte trifft.
"""

import json
import math
import urllib.error
import urllib.request

#: Mehrsprachig, 1024 Dimensionen. Gemessen am 06.08.2026: Deutsch,
#: Englisch und Ungarisch liefern je rund 650 ms. Das Portal führt vier
#: Sprachen — ein rein englisches Modell wäre hier die falsche Wahl.
MODELL = "bge-m3"

#: Grosszügig: Der Abruf dauert rund 650 ms, aber der Proxy steht
#: gelegentlich an. Lieber einmal warten als eine Lücke im Speicher.
ZEITGRENZE = 30.0


class Einbetter:
    """Was ein Einbetter können muss

    Eine Unterklasse ist nicht nötig — es genügt, ``einbetten`` mit dieser
    Signatur anzubieten. Die Klasse steht hier, damit die Erwartung an
    einer Stelle steht.
    """

    def einbetten(self, text):
        """Gibt den Vektor zu einem Text zurück, oder None

        Args:
            text (str): der einzubettende Text

        Returns:
            list[float] | None: der Vektor, oder None wenn nicht möglich
        """
        raise NotImplementedError


class OhneEinbetter(Einbetter):
    """Bettet nichts ein — der Speicher sucht dann im Volltext"""

    def einbetten(self, text):
        return None


class ProxyEinbetter(Einbetter):
    """Holt Vektoren vom QuiteQue-Proxy

    Args:
        url (str): Adresse des Proxys, etwa ``http://127.0.0.1:7077``
        token (str): Zugangsschlüssel
        nutzer (str): landet im Header ``X-OwlTrail-User``
        modell (str): Modellname, siehe :data:`MODELL`
    """

    def __init__(self, url, token, nutzer="", modell=MODELL):
        self.url = str(url or "").rstrip("/")
        self.token = token
        self.nutzer = nutzer
        self.modell = modell
        #: Beim ersten Fehlschlag merken wir uns das und hören auf zu
        #: fragen. Sonst wartet jede Suche erneut in die Zeitgrenze —
        #: bei zwanzig Textstücken sind das zehn Minuten Schweigen.
        self.abgeschaltet = False
        self.letzter_fehler = ""

    def einbetten(self, text):
        if self.abgeschaltet or not str(text or "").strip():
            return None
        daten = json.dumps({"input": text, "model": self.modell}).encode("utf8")
        anfrage = urllib.request.Request(
            self.url + "/v1/embeddings", data=daten,
            headers={
                "Authorization": "Bearer %s" % self.token,
                "X-OwlTrail-User": self.nutzer,
                "Content-Type": "application/json",
            })
        try:
            with urllib.request.urlopen(anfrage, timeout=ZEITGRENZE) as antwort:
                roh = json.load(antwort)
            return roh["data"][0]["embedding"]
        except (urllib.error.URLError, OSError, ValueError, KeyError,
                IndexError) as fehler:
            self.abgeschaltet = True
            self.letzter_fehler = str(fehler)
            return None


def aehnlichkeit(einer, anderer):
    """Kosinus zwischen zwei Vektoren, zwischen -1 und 1

    Gemessen mit ``bge-m3`` am 06.08.2026::

        FPGA-Erfahrung ↔ programmierbare Logik   0.627
        FPGA-Erfahrung ↔ "Absatz ist zu lang"    0.445

    Der Abstand ist schmaler, als man erwartet. Deshalb steht die
    Mindestähnlichkeit in :mod:`absicht.wissen.speicher` bei 0,5 und nicht
    bei 0,8 — wer hier zu streng schwellt, bekommt nie einen Treffer.

    Args:
        einer (list[float]): erster Vektor
        anderer (list[float]): zweiter Vektor

    Returns:
        float: 0.0 wenn einer der Vektoren leer oder eine Länge null hat
    """
    if not einer or not anderer or len(einer) != len(anderer):
        return 0.0
    oben = sum(x * y for x, y in zip(einer, anderer))
    links = math.sqrt(sum(x * x for x in einer))
    rechts = math.sqrt(sum(y * y for y in anderer))
    if not links or not rechts:
        return 0.0
    return oben / (links * rechts)
