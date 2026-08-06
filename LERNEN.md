# Wie die Absichten wachsen

Die Schicht fängt heute rund 30 % der Nachrichten ab. Die übrigen 70 %
laufen ans Modell — und niemand sieht sich an, was darin steckt. Genau
das holt `absicht/lernen.py` nach.

Der Bediener am 06.08.2026:

> *„Wie schaffen wir es, dass die Datenbank der vorgefertigten Fragen
> wächst? Kannst du ein Statistik-Zeug einarbeiten, dass wir hin und
> wieder mit dem System selber auswerten — an der und der Stelle hat der
> Nutzer immer da und da mit geantwortet. Damit wir den 30-Prozent-Teil
> grösser bekommen."*

## Der Ablauf

```
Betrieb  →  Protokoll  →  lernen.py  →  Vorschläge  →  Mensch entscheidet
                                                            ↓
                                                     absichten_de.yaml
```

Der letzte Pfeil ist von Hand. **Das Werkzeug ändert nichts.** Eine
Absicht, die sich selbst in die Datei schreibt, ist eine Absicht, die
niemand geprüft hat — und bei `folgenreich: true` verschickt so etwas
Bewerbungen.

## Anwendung

```bash
# Was liegt im Protokoll?
python -m absicht.lernen logs/absicht.jsonl

# Was könnte daraus werden?
python -m absicht.lernen logs/absicht.jsonl --vorschlaege

# Gründlicher: inhaltlich gruppieren statt über gemeinsame Wörter
python -m absicht.lernen logs/absicht.jsonl --vorschlaege --einbetten
```

Das Protokoll entsteht, sobald der Aufrufer es einrichtet:

```python
from absicht import protokoll
protokoll.in_datei("logs/absicht.jsonl")
```

## Zwei Arten zu gruppieren — und warum die zweite mehr findet

**Wörtlich** (Vorgabe): gemeinsame Kennworte, Füllwörter weg. Schnell,
kostet nichts, findet aber nur, was wörtlich ähnlich ist.

**Inhaltlich** (`--einbetten`): über `bge-m3`. Rund 650 ms je Nachricht —
bei zweihundert Nachrichten gut zwei Minuten. Deshalb nicht die Vorgabe.

Der Unterschied, gemessen an 110 echten durchgereichten Nachrichten:

Wörtlich fand **keine einzige** Gruppe ab drei Nachrichten. Inhaltlich
fand es zwei — und beide sind echte Absichten:

> **Gruppe 1** — dreimal dieselbe Bitte, dreimal anders formuliert:
> *„Hast du eine andere Nummer?"* · *„Ja; es ist viel; hast du eine neue
> Telefonnummer?"* · *„Hast du eine neue Handynummer?"*
>
> Gemeinsame Wörter: nur „hast" und „neue". Zu wenig für die wörtliche
> Suche, offensichtlich für die inhaltliche.

> **Gruppe 2** — dreimal dieselbe Beschwerde über einen doppelten
> Betreff im Anschreiben.

Das sind zwei Absichten, die den 30-Prozent-Teil wachsen lassen würden.
Ohne dieses Werkzeug hätte sie niemand gefunden.

## Was ein Vorschlag enthält

```yaml
  absicht_1:
    # Vorschlag aus 3 aehnlichen Nachrichten im Protokoll.
    # GEPRUEFT: nein — Absicht, Aktion und Schwellen fehlen.
    aktion: null
    folgenreich: false
    wendungen:
      - [hast, neue, nummer]
```

Drei Zeilen davon muss ein Mensch setzen, und keine davon kann ein
Werkzeug wissen:

- **Der Name.** `absicht_1` sagt nichts. Heißt es `kontakt_aendern`?
- **Die Aktion.** Was soll geschehen — nur antworten, oder die Nummer im
  Profil ändern?
- **`folgenreich`.** Ändert diese Absicht etwas, das man nicht
  zurücknehmen kann? Dann gilt 0,95 statt 0,80.

## Ab wann eine Gruppe zählt

Vorgabe: **drei** Nachrichten. Zwei sind ein Zufall, drei sind ein
Muster. Mit `--ab 2` sieht man auch die Zufälle — nützlich, wenn wenig
Material da ist, aber dann steht viel Rauschen in der Liste.

## Wann man es laufen lässt

Nicht täglich. Sinnvoll wird es, wenn seit dem letzten Mal ein paar
hundert Nachrichten dazugekommen sind — dann zeigen sich Muster, die
vorher Einzelfälle waren. Ein Blick im Monat genügt.
