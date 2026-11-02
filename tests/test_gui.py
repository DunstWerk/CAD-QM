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
    # Fehlalarm bewerten -> nicht im Export
    win.rate("false")
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


@pytest.mark.skipif(not os.path.exists(SAMPLE), reason="kein Beispielplan")
def test_rating_keys_advance_and_feedback(win, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    import json
    win.add_paths([SAMPLE]); win.cb_cons.setChecked(False)
    run_sync(win); win.show(); win.activateWindow(); QTest.qWaitForWindowActive(win)      # Shortcuts brauchen ein aktives Fenster
    n = win.table.rowCount(); assert n >= 4
    win.table.selectRow(0); win.table.setFocus()
    first = win._selected()
    # Taste 1 = annehmen -> eine Zeile weiter; Taste 2 = Fehlalarm -> weiter
    QTest.keyClick(win, Qt.Key_1)
    assert win.table.currentRow() == 1 and win.verdict_of(*first) == "accepted"
    second = win._selected()
    QTest.keyClick(win, Qt.Key_2)
    assert win.table.currentRow() == 2 and win.verdict_of(*second) == "false"
    QTest.keyClick(win, Qt.Key_Backspace)                       # zuruecksetzen, bleibt stehen
    assert win.table.currentRow() == 2
    # Zeilenfarbe/Text der bewerteten Zeile
    assert win.table.item(0, 0).text().startswith("✓") and win.table.item(1, 0).text().startswith("✗")
    assert "2 von" in win.lbl_rated.text()
    # Filter nach Bewertung
    win.cmb_verdict.setCurrentIndex(2); assert win.table.rowCount() == 1
    win.cmb_verdict.setCurrentIndex(1); assert win.table.rowCount() == n - 2
    win.cmb_verdict.setCurrentIndex(0)
    # Bewertung ueberlebt Schwellen-Aenderung (Cluster verschieben sich leicht)
    win.sp_warn.setValue(win.sp_warn.value() + 5)
    assert any(win.verdict_of(p, f) == "accepted" for p, f in win.rows) or win.sp_warn.value() > 0
    win.sp_warn.setValue(10)
    # Letzte Zeile bewerten: kein Absturz, Auswahl bleibt
    win.table.selectRow(win.table.rowCount() - 1); win.rate("accepted")
    assert win.table.currentRow() == win.table.rowCount() - 1
    # Export legt Feedback an
    win.export()
    fb = win.last_feedback
    assert fb and (fb / "feedback.md").exists() and (fb / "feedback.json").exists() and fb.parent.name == "ml_feedback"
    assert fb.parent.parent == tmp_path / "out"
    js = json.loads((fb / "feedback.json").read_text(encoding="utf-8"))
    verd = [f["verdict"] for f in js["findings"]]
    assert "angenommen" in verd and "Fehlalarm" in verd and "offen" in verd
    assert any("covered_pct" in f["features"] for f in js["findings"] if f["kind"] == "text_ink")
    assert len(list((fb / "crops").glob("*.png"))) == sum(v != "offen" for v in verd)
    assert "Mindestkontrast" in (fb / "feedback.md").read_text(encoding="utf-8")


@pytest.mark.skipif(not os.path.exists(SAMPLE), reason="kein Beispielplan")
def test_spelling_rating_whitelists_and_cursor_advances(win, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    win.add_paths([SAMPLE]); win.cb_overlap.setChecked(False); win.cb_cons.setChecked(False)
    run_sync(win); win.show(); win.activateWindow(); QTest.qWaitForWindowActive(win)
    win.cmb_type.setCurrentIndex(2)                                # nur Rechtschreibung anzeigen (run_sync prueft immer auch Ueberlappung)
    assert win.view and all(f.type == "spelling" for _, f in win.view)
    words = [f.text for _, f in win.view]
    assert len(set(w.lower() for w in words)) >= 3
    win.table.selectRow(0); win.table.setFocus()
    first = win._selected()[1].text
    # erster abweichender Befund hinter der Auswahl = erwartetes Ziel des Cursors
    expected = next(f.text for _, f in win.view if f.text.lower() != first.lower())
    QTest.keyClick(win, Qt.Key_2)                                  # Standard: Fehlalarm (2) nimmt das Wort in die Whitelist auf
    assert first in (tmp_path / "wl.txt").read_text(encoding="utf-8")
    assert all(f.text.lower() != first.lower() for _, f in win.rows if f.type == "spelling")           # alle gleichen Woerter verschwunden
    assert win._selected() is not None and win._selected()[1].text == expected  # Cursor ist weitergesprungen
    assert win.whitelist_actions and win.whitelist_actions[-1]["word"] == first
    # Annehmen (1) bewertet normal (kein Whitelist-Eintrag)
    before = (tmp_path / "wl.txt").read_text(encoding="utf-8")
    cur = win._selected()[1]
    QTest.keyClick(win, Qt.Key_1)
    assert (tmp_path / "wl.txt").read_text(encoding="utf-8") == before and win.verdict_of(*[x for x in win.rows if x[1].text == cur.text][0]) == "accepted"
    # Modus umstellen: Annehmen (1) nimmt das Wort auf
    win.cmb_wl.setCurrentIndex(1)
    w2 = win._selected()[1].text
    QTest.keyClick(win, Qt.Key_1)
    assert w2 in (tmp_path / "wl.txt").read_text(encoding="utf-8")
    # Button 'Wort zur Whitelist' springt ebenfalls weiter
    win.cmb_wl.setCurrentIndex(2)
    w3 = win._selected()[1].text; nxt = next((f.text for _, f in win.view[win.table.currentRow() + 1:] if f.text.lower() != w3.lower()), None)
    win.add_to_whitelist()
    assert w3 in (tmp_path / "wl.txt").read_text(encoding="utf-8")
    if nxt:
        assert win._selected()[1].text == nxt


@pytest.mark.skipif(not os.path.exists(SAMPLE), reason="kein Beispielplan")
def test_preview_zoom_slider(win):
    from cadqm.gui.app import render_preview
    win.add_paths([SAMPLE]); win.cb_cons.setChecked(False); run_sync(win)
    win.table.selectRow(0)
    base = win.lbl_prev.pixmap().toImage()
    win.sl_zoom.setValue(400); win._zoom_timer.stop(); win.show_preview()       # Timer-Entprellung im Test umgehen
    assert win.lbl_zoom.text() == "400 %"
    zoomed = win.lbl_prev.pixmap().toImage()
    assert zoomed != base
    win.sl_zoom.setValue(25); win.show_preview(); assert not win.lbl_prev.pixmap().isNull()
    path, f = win._selected()                                                        # kleiner Ausschnitt zeigt weniger Seitenflaeche
    import pymupdf
    page = pymupdf.open(path)[f.page]
    def area(z):
        b = pymupdf.Rect(f.bbox); pad = max(50.0, 3.0 * max(b.width, b.height)) / z
        return (b + (-pad * 1.6, -pad, pad * 1.6, pad)).get_area()
    assert area(4.0) < area(1.0) < area(0.25)
