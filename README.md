# CAD-QM

Lokale QM-Prüfung für PDF-CAD-Pläne (läuft komplett offline).

```bash
pip install -e ".[dev]"
cadqm check pfad/zum/plan_oder_ordner --out ausgabe/   # markierte PDFs (*_QM.pdf) + QM_Befunde.xlsx
cadqm smoke tests/data out/                            # Debug-PNGs: Tinte, Texte, Plankopf
cadqm eval-gt alt_ordner neu_ordner                    # Recall gegen von Hand markierte Stellen
```

Prüfungen: Überlagerung (Text↔Grafik, Text↔Text) – Rechtschreibung und Konsolidität folgen.
Markierungen liegen auf der PDF-Ebene „QM-Prüfung“ (ein-/ausblendbar): **Ü** Überlappung (orange), **R** Rechtschreibung (türkis), **K** Konsolidität (gold); durchgezogener Rahmen = Fehler, gestrichelt = Hinweis.
Schwellen und Farben: `config/default.yaml`. Beispielpläne liegen in `tests/data/` und sind nicht im Git.
