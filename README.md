# CAD-QM

Lokale QM-Prüfung für PDF-CAD-Pläne (läuft komplett offline).

```bash
pip install -e ".[dev,gui]"
cadqm gui [plan1.pdf plan2.pdf …]                    # Oberfläche (PySide6)
cadqm check pfad/zum/plan_oder_ordner --out ausgabe/   # markierte PDFs (*_QM.pdf) + QM_Befunde.xlsx
cadqm smoke tests/data out/                            # Debug-PNGs: Tinte, Texte, Plankopf
cadqm eval-gt alt_ordner neu_ordner                    # Recall gegen von Hand markierte Stellen
```

Prüfungen: Überlagerung (Text↔Grafik, Text↔Text), Rechtschreibung (Hunspell de_DE, offline), Konsolidität über den Plansatz (Ordner übergeben): Plannummer↔Dateiname, Index↔Indextabelle, Plankopf-Felder einheitlich, Schreibvarianten, Koten-Format, Legende. Plankopf-Beschriftungen je Vorlage in `config/default.yaml` unter `consistency.fields`.
Rechtschreibung: Fachwörter in `config/whitelist.txt` (oder `--whitelist datei.txt`) eintragen; `cadqm words <ordner>` listet die häufigsten unbekannten Wörter als Vorlage.
Wörterbuch `src/cadqm/data/de_DE/` (LibreOffice de_DE_frami) steht unter GPL 2/3 – bei Weitergabe der App beachten.
Markierungen liegen auf der PDF-Ebene „QM-Prüfung“ (ein-/ausblendbar): **Ü** Überlappung (orange), **R** Rechtschreibung (türkis), **K** Konsolidität (gold); durchgezogener Rahmen = Fehler, gestrichelt = Hinweis.
Schwellen und Farben: `config/default.yaml`. Beispielpläne liegen in `tests/data/` und sind nicht im Git.

## Oberfläche

`cadqm gui` (bzw. `cadqm-gui`): Pläne/Ordner laden → Prüfung starten → Befunde sichten → exportieren.
- **Schwellwerte** (links) wirken **sofort** auf die Ergebnisliste, ohne neu zu prüfen (Text von Grafik verdeckt: Hinweis/Fehler ab %; Text über Text). Nur der **Mindestkontrast** braucht eine neue Prüfung (Hinweis „neu prüfen“ erscheint).
- Zeile wählen → **Vorschau** mit Rahmen um die Fundstelle. Haken in der ersten Spalte entfernen = Fehlalarm, wird nicht exportiert.
- **Wort zur Whitelist hinzufügen** (bei Rechtschreibung) schreibt das Wort in die Whitelist-Datei und blendet es sofort aus.
- Linux-Hinweis: Qt braucht `libegl1`, `libgl1`, `libxkbcommon0` (auf Desktop-Systemen meist vorhanden).
