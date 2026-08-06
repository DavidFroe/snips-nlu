# Der Wissensspeicher

Die Absichtsschicht entscheidet, **ob** das Sprachmodell gebraucht wird.
Der Wissensspeicher entscheidet, **womit**.

Beides zusammen ergibt den Weg `aufbereitet`: nicht die immer gleichen
2.800 Token mitschleppen, sondern die drei Absätze, die zur Frage passen.

## Wo er im Ablauf steht

Nicht dazwischen — daneben:

```
Nachricht  →  ABSICHTSSCHICHT
                    │
      ┌─────────────┼─────────────────┐
      ▼             ▼                 ▼
   direkt      aufbereitet      durchreichen
      │             │                 │
  Antwort aus       └────────┬────────┘
  der Bibliothek             ▼
      │                WISSENSSPEICHER
      │                      ▼
      │                     LLM
      ▼                      ▼
         Antwort an den Bewerber
```

Beim Weg `direkt` kommt der Speicher nie vor. „Nein" braucht kein
Nachschlagen — das wäre 650 ms für eine Antwort, die in einer
Millisekunde dasteht.

## Die eine Regel

**Jeder Bewerber hat seinen eigenen Speicher, strikt getrennt.**

Das ist keine Ordnungsfrage. Landet ein Satz aus Davids Lebenslauf in
Tonis Anschreiben, steht in einem Dokument an einen Arbeitgeber eine
Behauptung über einen Menschen, die nicht stimmt. Das ist der Fehler,
nach dem man ein System abschaltet — nicht der, den man in der nächsten
Fassung behebt.

Deshalb im Code:

```python
Speicher(nutzer="", pfad=…)     # ValueError
```

Ein Speicher ohne Nutzernamen entsteht gar nicht erst. Es gibt keine
Abfrage über alle Nutzer, keinen gemeinsamen Index, kein „such mal
überall". Und die Datei trägt den Nutzernamen **in sich**: Eine
verschobene oder umbenannte Datei wird beim Laden abgewiesen, statt
stillschweigend als Speicher eines anderen durchzugehen.

## Was hineingehört

Was der Bewerber über sich erzählt hat, sein Lebenslauf, seine bisherigen
Anschreiben. Aus den echten Verläufen:

> *„Bei horizont group entwickelte ich Weidezaungeräte mit
> Hochspannungsgeneratoren"*
>
> *„bei FPGA Programierung hab ich Xilinx, Altera unsd Lattice gemacht"*

Diese Sätze wandern heute ins Nichts: Der Bewerber erzählt, das Modell
antwortet freundlich, und beim nächsten Anschreiben weiß niemand mehr,
dass er Lattice-FPGAs kann.

## Zwei Suchwege, absichtlich

**Mit Einbetter** findet er inhaltlich. Gemessen mit `bge-m3` am
06.08.2026:

| Vergleich | Ähnlichkeit |
|---|---:|
| FPGA-Erfahrung ↔ programmierbare Logik | **0,627** |
| FPGA-Erfahrung ↔ „Absatz ist zu lang" | 0,445 |

Der Abstand ist schmaler, als man erwartet. Deshalb steht die
Mindestähnlichkeit bei **0,5** und nicht bei 0,8 — wer hier zu streng
schwellt, bekommt nie einen Treffer.

**Ohne Einbetter** sucht er im Volltext: gemeinsame Wörter ab vier
Zeichen. Das findet weniger — „programmierbare Logik" trifft „FPGA"
nicht —, aber es findet.

Der Rückfall ist keine Verlegenheitslösung. Der Embedding-Endpunkt steht
in `QUITEQUE_INTERFACE.md` **nicht**. Er existiert und antwortet, wird
aber nur stillschweigend an Ollama durchgereicht — erkennbar an der
Fehlermeldung `model not found, try pulling it first`. Was nicht im
Vertrag steht, kann ohne Ankündigung verschwinden. Ein Wissensspeicher,
der dann gar nichts mehr liefert, ist schlechter als einer, der
Stichworte trifft.

## Das Modell

`bge-m3` über den QuiteQue-Proxy:

| | |
|---|---|
| Dimensionen | 1024 |
| Sprachen | mehrsprachig — Deutsch, Englisch, Ungarisch, Chinesisch geprüft |
| Dauer je Abruf | rund 650 ms |
| Arbeitsspeicher **auf dieser Maschine** | **0** |

Der letzte Punkt ist der wichtige: Das Modell läuft woanders. Auf der
Maschine des Bewerbungstrainers, die mit elf Containern und 1,2 GB
freiem Speicher fährt, kostet der Wissensspeicher kein Byte.

Die 650 ms fallen nur bei der **Frage** an. Die Textstücke werden einmal
beim Aufnehmen eingebettet und behalten ihren Vektor. Gegenüber 40 bis
107 Sekunden für einen Modellaufruf ist das nicht der Rede wert.

`nomic-embed-text` liegt ebenfalls bereit (768 Dimensionen), ist aber
primär englisch. Bei vier Portalsprachen ist das die falsche Wahl.

## Ablage

Eine JSON-Datei je Nutzer. Keine Vektordatenbank: Das wären eine weitere
Abhängigkeit, ein weiterer Dienst und ein weiteres Ding, das beim
nächsten Python-Sprung nicht mehr baut — genau der Grund, warum dieser
Fork überhaupt nötig war. Bei einem Bewerber reden wir über einige
hundert Textstücke; dafür genügt eine Liste im Arbeitsspeicher.

## Anwendung

```python
from absicht.wissen import Speicher, ProxyEinbetter

einbetter = ProxyEinbetter(url="http://127.0.0.1:7077",
                           token=…, nutzer="david")
speicher = Speicher("david", "user/david/.wissen.json", einbetter)

speicher.merken("Bei horizont group entwickelte ich Weidezaungeräte",
                quelle="chat", zeit="2026-08-06T12:00")
speicher.sichern()

for stueck, naehe in speicher.suchen("Erfahrung mit Hochspannung"):
    print(f"{naehe:.2f}  {stueck.text}")
```
