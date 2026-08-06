# Die Absichtsschicht

Ein Türsteher vor dem Sprachmodell. Für jede eingehende Bewerbernachricht
entscheidet sie in unter 10 ms, ob wir selbst antworten können, ob wir das
Modell mit vorbereitetem Auftrag rufen, oder ob wir alles durchreichen.

Heute geht jede Nachricht ungefiltert ans Modell — rund 11.000 Zeichen
Grundlast, etwa 2.800 Token, Antwortzeiten bis 107 Sekunden. Auch dann, wenn
ein Bewerber „Nein" schreibt. Vier Zeichen.

```python
import absicht

ergebnis = absicht.pruefen(
    text="nein, lieber die andere zuerst",
    nutzer="david",
    kontext={"ref": "0096", "letzte_frage": "freigabe"},
)
```

## Drei Wege, mehr nicht

```python
{"weg": "direkt",              # 1. Wir antworten selbst
 "absicht": "ablehnung",
 "sicherheit": 0.97,
 "antwort": "Verstanden, dann lassen wir die.",
 "aktion": {"art": "ablehnen", "ref": "0096"}}

{"weg": "aufbereitet",         # 2. Modell nötig, aber wir wissen wofür
 "absicht": "anschreiben_aendern",
 "sicherheit": 0.73,
 "llm_auftrag": {
     "zweck": "textaenderung",
     "prompt_bausteine": ["persona", "anschreiben_aktuell"],
     "weglassen": ["werkzeuge", "bewerbungsliste", "verhaltensregeln"],
     "extrakt": {"stelle": "letzter Absatz", "wunsch": "kuerzer"}}}

{"weg": "durchreichen",        # 3. Keine Ahnung — voller Kontext ans Modell
 "absicht": "",
 "sicherheit": 0.31}
```

**Der mittlere Fall ist der wertvollste.** Nur ein Teil der Nachrichten lässt
sich ohne Modell beantworten, aber ein großer Teil des Rests ist thematisch
eindeutig. Wer weiß, dass es um eine Textänderung geht, schickt Anschreiben
und Persona — und lässt Werkzeugliste, Bewerbungsübersicht und
Verhaltensregeln weg.

`sicherheit` ist die Sicherheit der **Erkennung**, nicht des Weges. Sie kann
hoch sein, obwohl durchgereicht wird — nämlich dann, wenn eine der Regeln
unten den kurzen Weg gesperrt hat. Warum, steht im Protokoll.

## Die zwei Regeln, die nicht verhandelbar sind

Ein Bewerber steht mitten im Freitextgespräch — er hat gefragt „Warum braucht
ihr das Zeugnis?", das Modell hat geantwortet — und schreibt dann „Ja".
Deutet die Schicht das als Freigabe, geht eine Bewerbung raus, die niemand
freigegeben hat.

| Regel | Wirkung |
|---|---|
| `offener_dialog: True` | für Absichten **mit Aktion** niemals `direkt` |
| keine `letzte_frage` im Kontext | ein „ja" ist bedeutungslos → `durchreichen` |

Dazu die harte Grenze im Erkenner: Steht ein Verneinungswort in der Nachricht,
ist `zustimmung` **ausgeschlossen** — unabhängig von jeder Sicherheit.
„Ja, aber nicht die erste" wird nie zur Freigabe. Das steht als
`verneinung_schliesst_aus` in den Absichtsdaten und wird von
`absicht/tests/test_sicherheit.py` an 30 Formulierungen × 4 Kontexten
geprüft. Fallen diese Tests, wird nichts ausgeliefert.

## Schwellen

| Sicherheit | was geschieht |
|---|---|
| ab 0,80 | `direkt`, wenn eine anwendbare Antwort hinterlegt ist |
| 0,50–0,79 | `aufbereitet` |
| unter 0,50 | `durchreichen` |
| **ab 0,95** | für Absichten mit Folgen (freigeben, abschicken, verwerfen) |

Alle vier stehen in `absicht/konfiguration.py` und lassen sich beim Laden
überschreiben — sie werden sich im Betrieb verschieben:

```python
from absicht.konfiguration import Konfiguration
absicht.laden(Konfiguration(schwelle_direkt=0.85))
```

## Die Dateien, die dem Bediener gehören

`absicht/daten/absichten_de.yaml` — welche Absichten es gibt, woran sie
erkannt werden, was sie auslösen. `absicht/daten/antworten_de.yaml` — die
Textbausteine. Beide lassen sich ändern, ohne eine Zeile Python anzufassen.

```yaml
ablehnung:
  aktion: ablehnen
  braucht_bezug: true      # ohne Bewerbung im Kontext nicht anwendbar
  kurzbefehle: [nein, nee, nö, nein danke, auf keinen fall]
  wendungen:
    - [lieber, nicht]
    - [andere, zuerst]
```

Mehrere Antworten je Absicht sind Absicht — ein System, das auf „danke" immer
denselben Satz sagt, wird nach dem dritten Mal als Maschine erkannt.
Platzhalter werden aus dem Kontext gefüllt; lässt sich einer nicht füllen,
fällt diese Antwort weg und eine andere kommt zum Zug. Halbe Sätze mit `{ref}`
darin gehen nicht raus.

## Wie erkannt wird

Ein Wörterbuch mit `difflib` — kein Modell, keine Abhängigkeit außer PyYAML.
Absteigend nach Stärke:

| | Beispiel | Sicherheit |
|---|---|---|
| Nachricht **ist** ein Kurzbefehl | „nein", „JO" | 0,97 |
| Nachricht ähnelt einem Kurzbefehl | „neee", „danek" | 0,80–0,96 |
| Nachricht **beginnt** mit einem | „Nein bitte die andere zuerst" | 0,88 |
| Wortgruppe kommt vor | „absatz" + „lang" | 0,60–0,90 |

Tippfehler: Wörter ab vier Buchstaben werden unscharf verglichen, kürzere
müssen exakt stimmen. **Die Grenze davon ist bekannt und gewollt:** Bei vier
Buchstaben liegt eine Vertauschung („nien" statt „nein") bei 75 %
Ähnlichkeit — genau dort, wo auch „kein" und „jein" liegen. Wer die Grenze so
weit senkt, liest irgendwann ein „jein" als „nein". Solche Nachrichten gehen
durch. Das kostet Token, löst aber nichts aus.

## Die Engine ist austauschbar

Das ist der Grund, warum die Schnittstelle zuerst gebaut wurde. Alles oberhalb
von `absicht/erkenner/` kennt nur `Treffer`:

```python
class MeinErkenner:
    def erkennen(self, text):
        return [Treffer(absicht="ablehnung", sicherheit=0.9,
                        begruendung="warum", extrakt={})]

absicht.laden(erkenner=MeinErkenner())
```

Kommt die portierte NLU-Engine, ersetzt sie das Wörterbuch **hinter** der
unveränderten Schnittstelle und muss sich an denselben Nachrichten messen
lassen. Ist sie nicht besser, bleibt das Wörterbuch.

## Messen

```bash
python -m absicht.bewerten nachrichten.jsonl --fehler
```

Eingabe ist eine Zeile JSON je Nachricht:

```json
{"text": "Nein bitte die andere zuerst", "absicht": "ablehnung", "kontext": {"ref": "0096"}}
```

Ausgegeben werden Trefferquote je Absicht, die Verteilung auf die drei Wege,
die Antwortzeit, die geschätzte Token-Ersparnis — und ob eine Ablehnung als
Zustimmung gelesen wurde. Passiert das, endet der Lauf mit Rückgabewert 1.

**Die 253 annotierten Nachrichten liegen noch nicht vor.** Bis dahin steht in
`absicht/daten/beispiele_de.jsonl` ein kleiner Satz aus den Beispielen, die in
den Anforderungsdokumenten wörtlich zitiert sind — 30 Nachrichten, 29 richtig
zugeordnet, 0,19 ms im Schnitt. Das zeigt, dass das Werkzeug läuft; über die
Trefferquote im Betrieb sagt es nichts.

Die eine Abweichung ist lehrreich: „Warum braucht ihr das Zeugnis überhaupt?"
ist als „durchreichen" annotiert, die Schicht erkennt `unterlagen` mit 0,70
und liefert `aufbereitet`. Das ist genau der mittlere Fall — thematisch
eindeutig, aber nicht selbst zu beantworten.

## Schattenbetrieb

Die Schicht schreibt nichts selbst auf die Platte, sie gibt jede Entscheidung
ans `logging` weiter. Für zwei Wochen Mitschnitt, eine Zeile JSON je
Nachricht:

```python
from absicht import protokoll
protokoll.in_datei("/var/log/absicht.jsonl")
```

Jeder Satz enthält Text, erkannte Absicht, Sicherheit, gewählten Weg, die drei
besten Kandidaten und **die Gründe** — auch die für eine unterdrückte
Entscheidung. Ohne das ist der Schattenbetrieb wertlos.

## Was sie nicht tut

Kein Zustand zwischen zwei Aufrufen. Kein Dialogmanager. Keine
Netzwerkzugriffe. Kein eigener Prozess, kein Container — sie wird als
Bibliothek importiert und läuft im Bot mit.

| | Ziel | gemessen |
|---|---|---|
| Antwortzeit | unter 10 ms | **0,19 ms** im Schnitt, 0,53 ms die langsamste |
| Arbeitsspeicher | unter 100 MB | **19 MB** für den ganzen Prozess (Python + PyYAML + die Schicht) |
| Abhängigkeiten | so wenige wie möglich | **PyYAML**, sonst Standardbibliothek |
| Sprachen | Deutsch zuerst | Deutsch; für weitere je eine Datei `absichten_<sprache>.yaml` |
