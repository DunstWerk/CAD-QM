import os
import pytest

pytest.importorskip("PySide6.QtWidgets")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication            # noqa: E402
from cadqm.gui.app import MainWindow, Worker          # noqa: E402

SAMPLE = "tests/data/v2/dtg.pdf"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    for n in ("information", "warning", "critical"):             # modale Dialoge wuerden den Test blockieren
        monkeypatch.setattr(QMessageBox, n, staticmethod(lambda *a, **k: None))
    from PySide6.QtCore import QSettings
    w = MainWindow(settings=QSettings(str(tmp_path / 'settings.ini'), QSettings.IniFormat))   # nie die echten Nutzereinstellungen anfassen
    w.ed_white.setText(str(tmp_path / "wl.txt")); w.ed_out.setText(str(tmp_path / "out"))
    yield w
    w.close(); w.deleteLater(); app.processEvents()               # sauber abbauen (Qt-Shutdown im Offscreen-Modus)


def run_sync(w):
    """Worker ohne Thread ausfuehren (deterministisch im Test)."""
    import copy
    cfg = copy.deepcopy(w.cfg)
    from cadqm.gui.app import RAW_WARN_FLOOR, RAW_TT_FLOOR
    cfg["overlap"].update(warn_pct=RAW_WARN_FLOOR, text_text_warn_pct=RAW_TT_FLOOR, contrast_min=w.sp_contrast.value())
    wk = Worker(list(w.files), cfg, ("overlap", "spelling"), [w.ed_white.text()])
    wk.done.connect(w._done); wk.failed.connect(w._failed)
    w.run_signature = w._signature()
    wk.run()


@pytest.mark.skipif(not os.path.exists(SAMPLE), reason="kein Beispielplan")
def test_threshold_filters_live_and_export(win, tmp_path):
    win.add_paths([SAMPLE]); win.cb_cons.setChecked(False)
    run_sync(win)
    assert win.rows, "keine Befunde"
    n_all = sum(1 for _, f in win.rows if f.type == "overlap")
    win.sp_warn.setValue(60); win.sp_err.setValue(90); win.sp_tt_warn.setValue(95); win.sp_tt_err.setValue(100)
    n_strict = sum(1 for _, f in win.rows if f.type == "overlap")
    assert n_strict < n_all                                         # hoehere Schwelle -> weniger Befunde, ohne neu zu pruefen
    win.sp_warn.setValue(1)
    assert sum(1 for _, f in win.rows if f.type == "overlap") >= n_all
    win.sp_err.setValue(0.5)                                         # Fehler-Schwelle darf nie unter Hinweis-Schwelle liegen
    assert win.sp_err.value() >= win.sp_warn.value()
    # Auswahl + Vorschau
    win.table.selectRow(0); assert win.lbl_prev.pixmap() is not None and not win.lbl_prev.pixmap().isNull()
    # Fehlalarm ausblenden -> nicht im Export
    win.toggle_selected()
    win.export()
    assert (tmp_path / "out" / "dtg_QM.pdf").exists() and (tmp_path / "out" / "QM_Befunde.xlsx").exists()
    import openpyxl
    ws = openpyxl.load_workbook(tmp_path / "out" / "QM_Befunde.xlsx").active
    assert ws.max_row - 1 == len(win.rows) - 1


@pytest.mark.skipif(not os.path.exists(SAMPLE), reason="kein Beispielplan")
def test_whitelist_button(win, tmp_path):
    win.add_paths([SAMPLE]); win.cb_overlap.setChecked(False); win.cb_cons.setChecked(False)
    run_sync(win)
    rows = [i for i, (_, f) in enumerate(win.view) if f.type == "spelling"]
    assert rows
    win.table.selectRow(rows[0]); word = win._selected()[1].text
    win.add_to_whitelist()
    assert word in (tmp_path / "wl.txt").read_text()
    assert all(f.text.lower() != word.lower() for _, f in win.rows if f.type == "spelling")


def test_stale_marker(win):
    win.add_paths([SAMPLE]) if os.path.exists(SAMPLE) else None
    win.run_signature = win._signature()
    win.sp_contrast.setValue(0.5)
    assert "neu prüfen" in win.lbl_stale.text()
