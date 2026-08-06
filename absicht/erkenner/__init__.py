"""Die Naht, an der die Erkennung ausgetauscht wird.

Alles oberhalb dieser Grenze — Schwellen, Antworten, die Regeln aus dem
Anforderungsdokument — kennt nur :class:`Treffer`. Ob darunter ein
Woerterbuch mit ``difflib``, ein trainierter Klassifikator oder eine
NLU-Engine arbeitet, ist von hier aus nicht zu sehen.

Das ist der ganze Zweck der Uebung: Snips 0.20.2 ist daran gestorben, dass
seine Datentypen ueberall durchgereicht wurden. Wer hier Engine-Typen nach
aussen gibt, macht denselben Fehler ein zweites Mal.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Treffer:
    """Eine erkannte Absicht mit ihrer Sicherheit

    Attributes:
        absicht (str): Name der Absicht, wie in den Absichtsdaten hinterlegt
        sicherheit (float): zwischen 0.0 und 1.0
        begruendung (str): warum es zu diesem Treffer kam, im Klartext.
            Landet im Protokoll — ohne das ist der Schattenbetrieb wertlos.
        extrakt (dict): was aus dem Text herausgelesen wurde, etwa
            ``{"stelle": "letzter Absatz", "wunsch": "kuerzer"}``
    """

    absicht: str
    sicherheit: float
    begruendung: str = ""
    extrakt: dict = field(default_factory=dict)


class Erkenner:
    """Was ein Erkenner koennen muss

    Eine Unterklasse ist nicht noetig — es genuegt, ``erkennen`` mit dieser
    Signatur anzubieten. Die Klasse steht hier, damit die Erwartung an einer
    Stelle steht und nicht in einem Kommentar verstreut ist.
    """

    def erkennen(self, text):
        """Bewertet einen Text gegen alle bekannten Absichten

        Args:
            text (str): Rohtext der Nachricht

        Returns:
            list[Treffer]: absteigend nach Sicherheit sortiert, moeglicherweise
                leer. Absichten ohne jeden Anhaltspunkt gehoeren nicht in die
                Liste.
        """
        raise NotImplementedError
