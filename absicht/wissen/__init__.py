"""Der Wissensspeicher — was wir über einen Bewerber wissen, abrufbar.

Die Absichtsschicht entscheidet, *ob* das Modell gebraucht wird. Dieses
Modul entscheidet, *womit*. Beides zusammen ergibt den Weg
``aufbereitet``: nicht die immer gleichen 2.800 Token mitschleppen,
sondern die drei Absätze, die zu dieser Frage passen.

## Wo es im Ablauf steht

Nicht dazwischen — daneben::

    Nachricht  →  ABSICHTSSCHICHT
                        |
          +-------------+-----------------+
          v             v                 v
       direkt      aufbereitet      durchreichen
          |             |                 |
      Antwort aus       +--------+--------+
      der Bibliothek             v
          |                  WISSENSSPEICHER
          |                       v
          |                      LLM
          v                       v
             Antwort an den Bewerber

Beim Weg ``direkt`` kommt der Speicher nie vor. „Nein" braucht kein
Nachschlagen.

## Die eine Regel, die nicht verhandelbar ist

**Jeder Bewerber hat seinen eigenen Speicher, strikt getrennt.**

Das ist keine Ordnungsfrage. Landet ein Satz aus Davids Lebenslauf in
Tonis Anschreiben, steht dort eine Behauptung über einen Menschen, die
nicht stimmt — in einem Dokument, das an einen Arbeitgeber geht. Das ist
der Fehler, nach dem man das System abschaltet.

Deshalb: `Speicher` wird **mit** einem Nutzernamen gebaut und kennt
keinen zweiten. Es gibt keine Abfrage über alle Nutzer, keinen
gemeinsamen Index, kein "such mal überall". Wer nutzerübergreifend
suchen will, muss zwei Speicher öffnen und weiß dann, was er tut.

## Was hineingehört

Was der Bewerber über sich erzählt hat, sein Lebenslauf, seine bisherigen
Anschreiben. Aus den echten Verläufen::

    „Bei horizont group entwickelte ich Weidezaungeräte mit
     Hochspannungsgeneratoren"
    „bei FPGA Programierung hab ich Xilinx, Altera unsd Lattice gemacht"

Diese Sätze wandern heute ins Nichts: Der Bewerber erzählt, das Modell
antwortet freundlich, und beim nächsten Anschreiben weiß niemand mehr,
dass er Lattice-FPGAs kann.

## Zwei Wege, absichtlich

``bge-m3`` über den Hausproxy — mehrsprachig (das Portal führt vier
Sprachen), 1024 Dimensionen, rund 650 ms je Abruf, und **kein Byte
Arbeitsspeicher auf dieser Maschine**, weil das Modell woanders läuft.

Fällt der Dienst aus, sucht der Speicher im Volltext weiter. Das findet
weniger, aber es findet. **Ein Wissensspeicher, der bei Netzproblemen gar
nichts liefert, ist schlechter als einer, der Stichworte trifft** — und
der Embedding-Endpunkt ist in `QUITEQUE_INTERFACE.md` nicht einmal
dokumentiert. Er wird stillschweigend an Ollama durchgereicht und kann
verschwinden, ohne dass jemand etwas ankündigt.
"""

from absicht.wissen.speicher import Speicher, Stueck
from absicht.wissen.einbetten import Einbetter, ProxyEinbetter, OhneEinbetter

__all__ = ["Speicher", "Stueck", "Einbetter", "ProxyEinbetter", "OhneEinbetter"]
