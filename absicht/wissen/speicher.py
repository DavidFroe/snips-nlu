"""Was wir über **einen** Bewerber wissen — abrufbar, nach Bedarf.

Ein Speicher gehört genau einem Nutzer. Es gibt keine Abfrage über alle,
keinen gemeinsamen Index, kein „such mal überall". Wer nutzerübergreifend
sucht, muss zwei Speicher öffnen und weiss dann, was er tut.

**Warum so streng:** Landet ein Satz aus Davids Lebenslauf in Tonis
Anschreiben, steht in einem Dokument an einen Arbeitgeber eine
Behauptung über einen Menschen, die nicht stimmt. Das ist der Fehler,
nach dem man ein System abschaltet — nicht der, den man in der nächsten
Fassung behebt.

## Zwei Suchwege

Mit Einbetter findet er inhaltlich: „Erfahrung mit programmierbarer
Logik" trifft „FPGA mit Xilinx und Lattice", obwohl kein Wort
übereinstimmt.

Ohne Einbetter sucht er im Volltext. Das findet weniger — aber es findet,
und der Einbetter hängt an einem Endpunkt, der nicht einmal dokumentiert
ist.

## Ablage

Eine JSON-Datei je Nutzer. Keine Vektordatenbank: Das wären eine weitere
Abhängigkeit, ein weiterer Dienst und ein weiteres Ding, das beim
nächsten Python-Sprung nicht mehr baut. Bei einem Bewerber reden wir über
einige hundert Textstücke — dafür genügt eine Liste im Arbeitsspeicher.
"""

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

from absicht.wissen.einbetten import OhneEinbetter, aehnlichkeit

#: Ab welcher Ähnlichkeit ein Stück als Treffer gilt.
#:
#: 0,5 wirkt niedrig, ist aber gemessen: ``bge-m3`` gibt verwandten
#: Sätzen 0,627 und fremden 0,445 — der Abstand ist schmaler als
#: erwartet. Wer hier 0,8 fordert, bekommt nie einen Treffer.
MINDEST_AEHNLICHKEIT = 0.5

#: Wie viele Stücke eine Suche höchstens zurückgibt. Der ganze Zweck ist,
#: den Prompt kleiner zu machen — wer zwanzig Absätze mitschickt, hat
#: nichts gewonnen.
HOECHSTENS = 3


@dataclass
class Stueck:
    """Ein Textstück im Speicher

    Attributes:
        text (str): der Inhalt
        quelle (str): woher es stammt — „lebenslauf", „chat", „anschreiben"
        ref (str): auf welche Bewerbung es sich bezieht, falls eine
        zeit (str): wann es entstand, als ISO-Zeichenkette
        vektor (list[float]): die Einbettung, leer wenn keine vorliegt
    """

    text: str
    quelle: str = ""
    ref: str = ""
    zeit: str = ""
    vektor: list = field(default_factory=list)


def _normalisieren(text):
    """Kleinschreibung ohne Satzzeichen — für die Volltextsuche"""
    t = unicodedata.normalize("NFC", str(text or "")).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\wäöüß\s]", " ", t)).strip()


class Speicher:
    """Der Wissensspeicher eines Bewerbers

    Args:
        nutzer (str): wessen Speicher das ist. Pflicht — ein Speicher ohne
            Nutzer gibt es nicht.
        pfad (Path): wohin die JSON-Datei geschrieben wird
        einbetter (Einbetter): wer Text zu Vektoren macht. Ohne Angabe
            arbeitet der Speicher im Volltext.

    Raises:
        ValueError: wenn kein Nutzername angegeben ist
    """

    def __init__(self, nutzer, pfad, einbetter=None):
        if not str(nutzer or "").strip():
            raise ValueError(
                "Ein Wissensspeicher gehoert immer genau einem Bewerber. "
                "Ohne Nutzernamen gibt es keinen.")
        self.nutzer = str(nutzer).strip()
        self.pfad = Path(pfad)
        self.einbetter = einbetter or OhneEinbetter()
        self.stuecke = []
        self._laden()

    # ── Ablage ──────────────────────────────────────────────────────────

    def _laden(self):
        try:
            roh = json.loads(self.pfad.read_text(encoding="utf8"))
        except (OSError, ValueError):
            return
        # Der Nutzername steht **in** der Datei und wird geprüft. Eine
        # verschobene oder falsch benannte Datei darf nicht stillschweigend
        # als Speicher eines anderen durchgehen.
        if str(roh.get("nutzer", "")) != self.nutzer:
            raise ValueError(
                "Die Datei %s gehoert dem Bewerber '%s', nicht '%s'."
                % (self.pfad, roh.get("nutzer", "?"), self.nutzer))
        self.stuecke = [Stueck(**s) for s in roh.get("stuecke", [])]

    def sichern(self):
        """Schreibt den Speicher auf die Platte"""
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        self.pfad.write_text(json.dumps({
            "nutzer": self.nutzer,
            "stuecke": [asdict(s) for s in self.stuecke],
        }, ensure_ascii=False, indent=2), encoding="utf8")

    # ── Füllen ──────────────────────────────────────────────────────────

    def merken(self, text, quelle="", ref="", zeit=""):
        """Nimmt ein Textstück auf

        Doppelte Texte werden übersprungen: Der Bewerber wiederholt sich,
        und dreimal derselbe Satz macht die Suche nicht besser, nur
        langsamer.

        Args:
            text (str): der Inhalt
            quelle (str): „lebenslauf", „chat", „anschreiben"
            ref (str): zugehörige Bewerbung, falls eine
            zeit (str): ISO-Zeitstempel

        Returns:
            Stueck | None: das aufgenommene Stück, oder None wenn leer
                oder schon vorhanden
        """
        text = str(text or "").strip()
        if not text:
            return None
        bekannt = _normalisieren(text)
        for vorhanden in self.stuecke:
            if _normalisieren(vorhanden.text) == bekannt:
                return None
        stueck = Stueck(text=text, quelle=quelle, ref=ref, zeit=zeit,
                        vektor=self.einbetter.einbetten(text) or [])
        self.stuecke.append(stueck)
        return stueck

    def nachtragen(self):
        """Bettet Stücke ein, die noch keinen Vektor haben

        Gebraucht, wenn der Speicher ohne Einbetter gefüllt wurde — etwa
        weil der Proxy nicht erreichbar war.

        Returns:
            int: wie viele Stücke einen Vektor bekommen haben
        """
        getan = 0
        for stueck in self.stuecke:
            if stueck.vektor:
                continue
            vektor = self.einbetter.einbetten(stueck.text)
            if vektor:
                stueck.vektor = vektor
                getan += 1
        return getan

    # ── Suchen ──────────────────────────────────────────────────────────

    def suchen(self, frage, hoechstens=HOECHSTENS, mindestens=None):
        """Die Textstücke, die zu dieser Frage passen

        Args:
            frage (str): wonach gesucht wird
            hoechstens (int): wie viele Stücke höchstens
            mindestens (float): Mindestähnlichkeit, siehe
                :data:`MINDEST_AEHNLICHKEIT`

        Returns:
            list[tuple[Stueck, float]]: Stücke mit ihrer Ähnlichkeit,
                absteigend sortiert
        """
        frage = str(frage or "").strip()
        if not frage or not self.stuecke:
            return []
        grenze = MINDEST_AEHNLICHKEIT if mindestens is None else mindestens

        vektor = self.einbetter.einbetten(frage)
        if vektor:
            bewertet = [
                (s, aehnlichkeit(vektor, s.vektor))
                for s in self.stuecke if s.vektor]
            if bewertet:
                bewertet.sort(key=lambda p: p[1], reverse=True)
                return [(s, w) for s, w in bewertet
                        if w >= grenze][:hoechstens]

        return self._volltext(frage, hoechstens)

    def _volltext(self, frage, hoechstens):
        """Der Rückfall: gemeinsame Wörter zählen

        Findet weniger als eine Einbettung — „programmierbare Logik" trifft
        „FPGA" nicht. Aber es findet, und das ist mehr, als ein
        ausgefallener Dienst liefert.

        **Teilwörter zählen mit**, und zwar wegen der Sprache: „Weidezaun"
        steckt in „Weidezaungeräte", „Bordnetz" in
        „Bordnetzarchitektur". Ein Abgleich auf ganze Wörter findet im
        Deutschen die Hälfte nicht — genau das ist beim ersten Test
        passiert. Ein Teiltreffer wiegt weniger als ein voller, sonst
        würde „Netz" jedes Wort mit „netz" darin gleich stark bewerten.
        """
        gesucht = set(_normalisieren(frage).split())
        # Wörter unter vier Zeichen sind meist Füllwörter und verwässern
        # die Wertung ("mit", "der", "und").
        gesucht = {w for w in gesucht if len(w) >= 4}
        if not gesucht:
            return []
        bewertet = []
        for stueck in self.stuecke:
            worte = set(_normalisieren(stueck.text).split())
            wert = 0.0
            for wort in gesucht:
                if wort in worte:
                    wert += 1.0
                elif any(wort in w or w in wort for w in worte):
                    wert += 0.6
            if wert:
                bewertet.append((stueck, wert / len(gesucht)))
        bewertet.sort(key=lambda p: p[1], reverse=True)
        return bewertet[:hoechstens]

    def __len__(self):
        return len(self.stuecke)

    def __repr__(self):
        mit = sum(1 for s in self.stuecke if s.vektor)
        return "<Speicher %r: %d Stuecke, %d eingebettet>" % (
            self.nutzer, len(self.stuecke), mit)
