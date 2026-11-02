"""Selbsttest der (gebuendelten) App: prueft Abhaengigkeiten, Daten, Pruefungen, Export und GUI-Start ohne Beispielplaene."""
from __future__ import annotations
import os
import tempfile
import traceback
from pathlib import Path


def run(out_file: str | None = None) -> int:
    lines: list[str] = []
    ok = True

    def step(name, fn):
        nonlocal ok
        try:
            lines.append(f"OK    {name}: {fn()}")
        except Exception:                                         # noqa: BLE001
            ok = False
            lines.append(f"FEHLER {name}:\n{traceback.format_exc()}")

    tmp = Path(tempfile.mkdtemp(prefix="cadqm_selftest_"))
    state: dict = {}

    def _config():
        from .config import load_config
        state["cfg"] = cfg = load_config()
        return f"{len(cfg)} Abschnitte"

    def _dict():
        from .checks.spelling import _known
        assert _known("Kabelweg") and not _known("Requsite")
        return "Hunspell de_DE geladen"

    def _pdf():
        import pymupdf
        d = pymupdf.open(); p = d.new_page(width=600, height=400)
        p.insert_text((100, 200), "Kabelweg Requsite", fontsize=12, color=(0, 0, 0))
        p.insert_text((105, 203), "Steckdose", fontsize=12, color=(0, 0, 1))             # Text ueber Text
        p.draw_line((95, 197), (260, 197), color=(0, 0, 0), width=2)                      # Linie durch Text
        p.insert_text((450, 40), "Legende", fontsize=8)
        d.save(tmp / "t.pdf"); return str(tmp / "t.pdf")

    def _check():
        from .runner import check_set_files
        res = check_set_files([str(tmp / "t.pdf")], state["cfg"])
        fs = res[str(tmp / "t.pdf")]
        kinds = {f.kind for f in fs}
        assert "text_ink" in kinds and "text_text" in kinds and "typo" in kinds, kinds
        state["fs"] = fs
        return f"{len(fs)} Befunde ({', '.join(sorted(kinds))})"

    def _export():
        import pymupdf
        from .cluster import cluster
        from .report.feedback import write_feedback
        from .report.listing import write_xlsx
        from .report.markup import add_markup, add_summary
        fs = cluster(state["fs"]); cfg = state["cfg"]
        doc = pymupdf.open(tmp / "t.pdf"); add_markup(doc, fs, cfg); add_summary(doc, fs, cfg, "t"); doc.save(tmp / "t_QM.pdf")
        write_xlsx([("t", f) for f in fs], str(tmp / "t.xlsx"))
        fb = write_feedback(tmp, [(str(tmp / "t.pdf"), f, "accepted") for f in fs], {"settings": {}, "plans": []}, [], cfg["markup"]["colors"])
        assert (tmp / "t_QM.pdf").exists() and (tmp / "t.xlsx").exists() and (fb / "feedback.md").exists() and any((fb / "crops").iterdir())
        return "markiertes PDF, Excel, Feedback (inkl. Bildausschnitte)"

    def _gui():
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication
        from .gui.app import MainWindow, render_preview
        app = QApplication.instance() or QApplication([])
        w = MainWindow(settings=QSettings(str(tmp / "s.ini"), QSettings.IniFormat))
        w.add_paths([str(tmp / "t.pdf")])
        pm = render_preview(str(tmp / "t.pdf"), 0, (100, 190, 160, 205), (1, .5, 0))
        assert not pm.isNull()
        w.close()
        return "Fenster + Vorschau"

    for n, f in (("Konfiguration", _config), ("Wörterbuch", _dict), ("Test-PDF", _pdf), ("Prüfungen", _check), ("Export", _export), ("Oberfläche", _gui)):
        step(n, f)
    lines.append("SELFTEST OK" if ok else "SELFTEST FEHLGESCHLAGEN")
    text = "\n".join(lines)
    try:
        print(text)
    except Exception:                                             # noqa: BLE001 - Fenster-exe hat evtl. kein stdout
        pass
    if out_file:
        Path(out_file).write_text(text, encoding="utf-8")
    return 0 if ok else 1
