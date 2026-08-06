"""Nachvollziehbare Entscheidungen — die Voraussetzung fuer den Schattenbetrieb.

Zwei Wochen mitlaufen, ohne zu entscheiden, und mitschreiben, was die Schicht
entschieden haette: Daraus kommen die echten Trainingsdaten. Ohne ein
Protokoll, das Text, erkannte Absicht, Sicherheit, gewaehlten Weg **und den
Grund** enthaelt, ist dieser Betrieb wertlos.

Die Schicht schreibt selbst nichts auf die Platte. Sie gibt den Satz an das
``logging`` des Aufrufers weiter; wohin er geht, entscheidet der Aufrufer.
Fuer den haeufigsten Fall — eine Zeile JSON je Nachricht — steht
:func:`in_datei` bereit.
"""

import json
import logging
from datetime import datetime

PROTOKOLL = logging.getLogger("absicht")


def satz(text, nutzer, kontext, ergebnis, treffer, gruende):
    """Baut den Protokollsatz einer Entscheidung

    Returns:
        dict: alles, was noetig ist, um die Entscheidung spaeter
            nachzuvollziehen oder zu bestreiten
    """
    return {
        "zeit": datetime.now().isoformat(timespec="milliseconds"),
        "nutzer": nutzer,
        "text": text,
        "weg": ergebnis["weg"],
        "absicht": ergebnis.get("absicht") or None,
        "sicherheit": ergebnis.get("sicherheit"),
        "gruende": list(gruende),
        "kandidaten": [
            {"absicht": t.absicht,
             "sicherheit": t.sicherheit,
             "begruendung": t.begruendung}
            for t in treffer[:3]
        ],
        "kontext": dict(kontext or {}),
    }


def schreiben(satz_):
    """Gibt den Satz an das Logging weiter"""
    PROTOKOLL.info(
        "%s -> %s (%s, %.2f)",
        satz_["text"], satz_["weg"], satz_["absicht"] or "keine Absicht",
        satz_["sicherheit"] or 0.0,
        extra={"absicht_protokoll": satz_})


class _JsonZeilen(logging.Formatter):
    """Schreibt den Protokollsatz als eine Zeile JSON"""

    def format(self, record):
        satz_ = getattr(record, "absicht_protokoll", None)
        if satz_ is None:
            return super(_JsonZeilen, self).format(record)
        return json.dumps(satz_, ensure_ascii=False, sort_keys=True)


def in_datei(pfad, stufe=logging.INFO):
    """Haengt einen Mitschnitt an, eine Zeile JSON je Entscheidung

    Args:
        pfad (str oder Path): wohin geschrieben wird, im Anhaengemodus
        stufe (int): ab welcher Logging-Stufe mitgeschrieben wird

    Returns:
        logging.Handler: zum spaeteren Abhaengen mit
            ``PROTOKOLL.removeHandler(...)``
    """
    handler = logging.FileHandler(str(pfad), encoding="utf8")
    handler.setFormatter(_JsonZeilen())
    handler.setLevel(stufe)
    PROTOKOLL.setLevel(stufe)
    PROTOKOLL.addHandler(handler)
    return handler
