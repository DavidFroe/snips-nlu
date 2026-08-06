"""Die portierte NLU-Engine hinter derselben Schnittstelle.

Schritt 3 aus dem Auftrag: Die Engine ersetzt das Woerterbuch **hinter** der
unveraenderten Schnittstelle. Oberhalb von :mod:`absicht.erkenner` aendert
sich dafuer keine Zeile — weder die Schwellen noch die Antwortbibliothek noch
die harte Grenze bei einer Verneinung, die in
:func:`absicht.entscheidung.verneinung_sperrt` ueber der Naht steht und
deshalb auch fuer diesen Erkenner gilt.

Trainiert wird aus denselben Absichtsdaten, die auch das Woerterbuch benutzt:
Kurzbefehle und Wortgruppen werden zu Beispielsaetzen. Das sind zehn bis
zwanzig je Absicht — die Groessenordnung, die im Anforderungsdokument als
Trainingsaufwand steht.

    from absicht.erkenner.snips import SnipsErkenner
    erkenner = SnipsErkenner.trainieren(schicht.absichten)
    erkenner.sichern("/opt/bewerbungstrainer/absicht-engine")

    absicht.laden(erkenner=SnipsErkenner.laden(
        "/opt/bewerbungstrainer/absicht-engine"))

Ob sie das Woerterbuch schlaegt, entscheidet nicht die Bauart, sondern die
Messung an denselben Nachrichten::

    python -m absicht.bewerten nachrichten.jsonl

Ist sie nicht besser, bleibt das Woerterbuch.
"""

from absicht import extraktion
from absicht.erkenner import Treffer
from absicht.normalisierung import normalisieren

# Beide Seiten arbeiten auf derselben geglaetteten Form: trainiert wird mit
# normalisierten Beispielsaetzen, also wird auch normalisiert geparst. Sonst
# faellt jede Grossschreibung und jeder Umlaut auseinander.
SPRACHEN = {"de": "de", "en": "en", "fr": "fr", "es": "es", "it": "it",
            "pt": "pt_pt", "ja": "ja", "ko": "ko"}


def datensatz_bauen(absichten, sprache="de"):
    """Macht aus den Absichtsdaten einen Trainingsdatensatz fuer Snips

    Args:
        absichten (dict[str, Absicht]): dieselben Definitionen, aus denen das
            Woerterbuch arbeitet
        sprache (str): Sprachkuerzel, wie es die Engine erwartet

    Returns:
        dict: ein Datensatz im Snips-Format
    """
    intents = dict()
    for name, definition in absichten.items():
        saetze = list(definition.kurzbefehle)
        saetze.extend(" ".join(w.woerter) for w in definition.wendungen)
        saetze = [s for s in dict.fromkeys(saetze) if s]
        if not saetze:
            continue
        intents[name] = {
            "utterances": [{"data": [{"text": satz}]} for satz in saetze]}

    return {
        "intents": intents,
        "entities": dict(),
        "language": SPRACHEN.get(sprache, sprache),
    }


class SnipsErkenner:
    """Erkennung ueber eine trainierte Snips-NLU-Engine"""

    def __init__(self, engine):
        """
        Args:
            engine (SnipsNLUEngine): eine trainierte Engine
        """
        self.engine = engine

    @classmethod
    def trainieren(cls, absichten, sprache="de", random_state=None):
        """Trainiert eine Engine aus den Absichtsdaten

        Args:
            absichten (dict[str, Absicht]): siehe :mod:`absicht.absichten`
            sprache (str): welche Sprachressourcen benutzt werden
            random_state (int, optional): fuer wiederholbare Laeufe

        Returns:
            SnipsErkenner: mit trainierter Engine
        """
        from snips_nlu import SnipsNLUEngine

        datensatz = datensatz_bauen(absichten, sprache)
        engine = SnipsNLUEngine(random_state=random_state).fit(datensatz)
        return cls(engine)

    @classmethod
    def laden(cls, pfad):
        """Laedt eine gesicherte Engine"""
        from snips_nlu import SnipsNLUEngine

        return cls(SnipsNLUEngine.from_path(pfad))

    def sichern(self, pfad):
        """Schreibt die Engine an einen Pfad, der noch nicht existiert"""
        self.engine.persist(pfad)

    def erkennen(self, text):
        """Bewertet einen Text gegen alle trainierten Absichten

        Returns:
            list[Treffer]: absteigend nach Sicherheit sortiert
        """
        nachricht = normalisieren(text or "")
        if not nachricht:
            return []

        erkannte = [e for e in self.engine.get_intents(nachricht)
                    if e.get("intentName")]
        if not erkannte:
            return []

        # Die Slots werden genau einmal geholt, nicht je Absicht: ``parse``
        # laesst die ganze Kette laufen, und achtmal dasselbe zu tun kostete
        # mehr als das Zehn-Millisekunden-Ziel hergibt.
        schlitze = self._schlitze(nachricht)

        treffer = []
        for rang, erkannt in enumerate(erkannte):
            name = erkannt["intentName"]
            sicherheit = float(erkannt.get("probability") or 0.0)
            extrakt = dict(extraktion.auslesen(name, text, nachricht))
            if rang == 0:
                # Die Slots gehoeren zur Absicht, fuer die geparst wurde.
                for schluessel, wert in schlitze.items():
                    extrakt.setdefault(schluessel, wert)
            treffer.append(Treffer(
                absicht=name,
                sicherheit=round(sicherheit, 4),
                begruendung="Snips-Engine: %.0f %% fuer '%s'"
                            % (sicherheit * 100, name),
                extrakt=extrakt,
            ))
        return treffer

    def _schlitze(self, nachricht):
        """Die Slots, die die Engine aus der Nachricht gezogen hat

        Solange die Absichtsdaten keine Slots enthalten, ist das leer. Die
        Angaben, die auch das Woerterbuch herausliest — welche Stelle,
        welcher Wunsch — kommen unabhaengig davon dazu, damit der Weg
        "aufbereitet" auf beiden Seiten gleich viel traegt.
        """
        geparst = self.engine.parse(nachricht)
        return {
            s["slotName"]: s.get("rawValue")
            for s in (geparst.get("slots") or [])
            if s.get("slotName")}
