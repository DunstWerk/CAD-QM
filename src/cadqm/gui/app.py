"""CAD-QM Oberflaeche (PySide6): Plaene laden, pruefen, Schwellwerte live einstellen, Befunde sichten, exportieren."""
from __future__ import annotations
import copy
import os
import sys
from pathlib import Path

import pymupdf
from PySide6.QtCore import QObject, QSettings, Qt, QThread, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox,
                               QProgressBar, QPushButton, QScrollArea, QSlider, QSpinBox, QSplitter, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..cluster import cluster
from ..config import load_config
from ..findings import CONSISTENCY, OVERLAP, SPELLING, Finding
from ..report.listing import write_xlsx
from ..report.markup import TYPE_NAME, add_markup, add_summary
from ..runner import Cancelled, check_set_files
from ..thresholds import apply_thresholds

RAW_WARN_FLOOR, RAW_TT_FLOOR = 1.0, 5.0        # Rohlauf mit sehr niedrigen Schwellen; die GUI stuft danach live ein
SEV_NAME = {"error": "Fehler", "warn": "Hinweis"}


class Worker(QThread):
    progress = Signal(int, int, str)
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, files, cfg, checks, whitelist):
        super().__init__()
        self.files, self.cfg, self.checks, self.whitelist = files, cfg, checks, whitelist
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            res = check_set_files(self.files, self.cfg, self.checks, self.whitelist,
                                  progress=lambda i, n, m: self.progress.emit(i, n, m), cancelled=lambda: self._cancel)
            self.done.emit(res)
        except Cancelled:
            self.failed.emit("Abgebrochen")
        except Exception as e:                                   # noqa: BLE001 - Fehler dem Nutzer zeigen
            self.failed.emit(f"{type(e).__name__}: {e}")


def render_preview(path: str, page_no: int, bbox, color, width_px: int = 560) -> QPixmap:
    """Ausschnitt um den Befund aus dem ORIGINAL-PDF, Befund umrahmt."""
    doc = pymupdf.open(path)
    page = doc[page_no]
    b = pymupdf.Rect(bbox)
    pad = max(50.0, 3.0 * max(b.width, b.height))
    clip = (b + (-pad * 1.6, -pad, pad * 1.6, pad)) & page.rect
    zoom = min(8.0, width_px / max(clip.width, 1.0))
    pm = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, colorspace=pymupdf.csRGB, alpha=False, annots=False)
    img = QImage(pm.samples, pm.width, pm.height, pm.stride, QImage.Format_RGB888).copy()
    qp = QPainter(img)
    qp.setPen(QPen(QColor(*[int(c * 255) for c in color]), 3))
    qp.drawRect(int((b.x0 - clip.x0) * zoom) - 3, int((b.y0 - clip.y0) * zoom) - 3, int(b.width * zoom) + 6, int(b.height * zoom) + 6)
    qp.end()
    return QPixmap.fromImage(img)


class MainWindow(QMainWindow):
    def __init__(self, cfg: dict | None = None, settings: QSettings | None = None):
        super().__init__()
        self.cfg = cfg or load_config()
        self.settings = settings or QSettings("theapro", "CAD-QM")      # Tests uebergeben eigene, isolierte Einstellungen
        self.files: list[str] = []
        self.raw: dict[str, list[Finding]] = {}
        self.rows: list[tuple[str, Finding]] = []
        self.ignored: set[tuple] = set()
        self.session_whitelist: set[str] = set()
        self.worker: Worker | None = None
        self.run_signature: tuple | None = None
        self.setWindowTitle("CAD-QM – Planprüfung")
        self.resize(1500, 900)
        self._build()
        self._load_settings()
        self._update_state()

    # ------------------------------------------------------------------ UI
    def _build(self):
        o = self.cfg["overlap"]
        # --- links: Plaene + Einstellungen
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        b_add, b_dir, b_rm = QPushButton("Dateien …"), QPushButton("Ordner …"), QPushButton("Entfernen")
        b_add.clicked.connect(self.add_files); b_dir.clicked.connect(self.add_folder); b_rm.clicked.connect(self.remove_files)
        fb = QHBoxLayout(); [fb.addWidget(b) for b in (b_add, b_dir, b_rm)]
        g_files = QGroupBox("Pläne (PDF)"); lf = QVBoxLayout(g_files); lf.addWidget(self.file_list); lf.addLayout(fb)

        self.cb_overlap = QCheckBox("Überlappung"); self.cb_spell = QCheckBox("Rechtschreibung"); self.cb_cons = QCheckBox("Konsolidität (Plansatz)")
        for c in (self.cb_overlap, self.cb_spell, self.cb_cons):
            c.setChecked(True); c.toggled.connect(self._settings_changed)
        g_checks = QGroupBox("Prüfungen"); lc = QVBoxLayout(g_checks); [lc.addWidget(c) for c in (self.cb_overlap, self.cb_spell, self.cb_cons)]

        def pct_spin(val):
            sp = QDoubleSpinBox(); sp.setRange(0, 100); sp.setDecimals(1); sp.setSingleStep(1.0); sp.setSuffix(" %"); sp.setValue(val)
            return sp
        self.sp_warn, self.sp_err = pct_spin(o["warn_pct"]), pct_spin(o["error_pct"])
        self.sp_tt_warn, self.sp_tt_err = pct_spin(o["text_text_warn_pct"]), pct_spin(o["text_text_error_pct"])
        self.sl_warn = QSlider(Qt.Horizontal); self.sl_warn.setRange(0, 1000)
        self.sl_err = QSlider(Qt.Horizontal); self.sl_err.setRange(0, 1000)
        for sp, sl in ((self.sp_warn, self.sl_warn), (self.sp_err, self.sl_err)):
            sl.setValue(int(sp.value() * 10))
            sl.valueChanged.connect(lambda v, s=sp: s.setValue(v / 10))
            sp.valueChanged.connect(lambda v, s=sl: s.setValue(int(v * 10)))
        for sp in (self.sp_warn, self.sp_err, self.sp_tt_warn, self.sp_tt_err):
            sp.valueChanged.connect(self._thresholds_changed)
        self.sp_contrast = QDoubleSpinBox(); self.sp_contrast.setRange(0.05, 0.9); self.sp_contrast.setSingleStep(0.05)
        self.sp_contrast.setDecimals(2); self.sp_contrast.setValue(o["contrast_min"])
        self.sp_contrast.setToolTip("Mindest-Helligkeitsunterschied zwischen Text und Hintergrund (0–1). Höher = strenger.")
        self.sp_contrast.valueChanged.connect(self._settings_changed)
        g_th = QGroupBox("Schwellwerte Überlappung (wirken sofort)")
        form = QFormLayout(g_th)
        form.addRow(QLabel("<b>Text von Grafik verdeckt</b> (Anteil unlesbarer Textpixel)"))
        form.addRow("Hinweis ab", self.sp_warn); form.addRow("", self.sl_warn)
        form.addRow("Fehler ab", self.sp_err); form.addRow("", self.sl_err)
        form.addRow(QLabel("<b>Text über Text</b> (Boxüberlappung)"))
        form.addRow("Hinweis ab", self.sp_tt_warn); form.addRow("Fehler ab", self.sp_tt_err)
        form.addRow(QLabel("<b>Kontrast</b> (nur beim Prüfen, <i>neu prüfen nötig</i>)"))
        form.addRow("Mindestkontrast", self.sp_contrast)

        self.ed_white = QLineEdit(); self.ed_white.setPlaceholderText("Whitelist-Datei (ein Wort pro Zeile)")
        b_wf = QPushButton("…"); b_wf.setMaximumWidth(32); b_wf.clicked.connect(self.pick_whitelist)
        self.ed_out = QLineEdit(); self.ed_out.setPlaceholderText("Ausgabeordner")
        b_of = QPushButton("…"); b_of.setMaximumWidth(32); b_of.clicked.connect(self.pick_outdir)
        g_io = QGroupBox("Dateien"); fi = QFormLayout(g_io)
        rw = QHBoxLayout(); rw.addWidget(self.ed_white); rw.addWidget(b_wf); fi.addRow("Whitelist", rw)
        ro = QHBoxLayout(); ro.addWidget(self.ed_out); ro.addWidget(b_of); fi.addRow("Ausgabe", ro)

        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0)
        for w in (g_files, g_checks, g_th, g_io):
            ll.addWidget(w)
        ll.addStretch(1)

        # --- Mitte: Befundtabelle + Filter
        self.cmb_type = QComboBox(); self.cmb_type.addItems(["Alle Typen"] + list(TYPE_NAME.values()))
        self.cb_only_err = QCheckBox("nur Fehler"); self.ed_search = QLineEdit(); self.ed_search.setPlaceholderText("Suchen (Text, Plan, Beschreibung) …")
        self.lbl_count = QLabel("")
        for w, sig in ((self.cmb_type, self.cmb_type.currentIndexChanged), (self.cb_only_err, self.cb_only_err.toggled),
                       (self.ed_search, self.ed_search.textChanged)):
            sig.connect(lambda *_: self.refresh())
        fl = QHBoxLayout(); [fl.addWidget(w) for w in (self.cmb_type, self.cb_only_err, self.ed_search)]; fl.addWidget(self.lbl_count)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["✓", "Index", "Plan", "Typ", "Schwere", "Wert", "Text", "Beschreibung"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.table.verticalHeader().hide()
        hh = self.table.horizontalHeader(); hh.setSectionResizeMode(7, QHeaderView.Stretch); hh.setSectionResizeMode(6, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 30); self.table.setColumnWidth(1, 62); self.table.setColumnWidth(2, 125); self.table.setColumnWidth(3, 95)
        self.table.setColumnWidth(4, 70); self.table.setColumnWidth(5, 60); self.table.setColumnWidth(6, 150)
        self.table.itemSelectionChanged.connect(self.show_preview); self.table.itemChanged.connect(self._item_changed)
        mid = QWidget(); lm = QVBoxLayout(mid); lm.setContentsMargins(0, 0, 0, 0); lm.addLayout(fl); lm.addWidget(self.table)

        # --- rechts: Vorschau
        self.lbl_prev = QLabel("Befund auswählen …"); self.lbl_prev.setAlignment(Qt.AlignCenter); self.lbl_prev.setMinimumSize(420, 300)
        sc = QScrollArea(); sc.setWidget(self.lbl_prev); sc.setWidgetResizable(True)
        self.lbl_info = QLabel(""); self.lbl_info.setWordWrap(True); self.lbl_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.btn_white = QPushButton("Wort zur Whitelist hinzufügen"); self.btn_white.clicked.connect(self.add_to_whitelist)
        self.btn_false = QPushButton("Als Fehlalarm ausblenden / wieder einblenden"); self.btn_false.clicked.connect(self.toggle_selected)
        right = QWidget(); lr = QVBoxLayout(right); lr.setContentsMargins(0, 0, 0, 0)
        lr.addWidget(QLabel("<b>Vorschau</b>")); lr.addWidget(sc, 1); lr.addWidget(self.lbl_info); lr.addWidget(self.btn_white); lr.addWidget(self.btn_false)

        split = QSplitter(); split.addWidget(left); split.addWidget(mid); split.addWidget(right)
        split.setStretchFactor(0, 0); split.setStretchFactor(1, 3); split.setStretchFactor(2, 2); split.setSizes([330, 780, 400])

        # --- unten: Start/Fortschritt/Export
        self.btn_run = QPushButton("Prüfung starten"); self.btn_run.clicked.connect(self.start)
        self.btn_cancel = QPushButton("Abbrechen"); self.btn_cancel.clicked.connect(self.cancel); self.btn_cancel.setEnabled(False)
        self.btn_export = QPushButton("Exportieren (PDF + Excel) …"); self.btn_export.clicked.connect(self.export)
        self.progress = QProgressBar(); self.progress.setRange(0, 1); self.progress.setValue(0)
        self.lbl_status = QLabel("Bereit"); self.lbl_stale = QLabel(""); self.lbl_stale.setStyleSheet("color:#b25e00;font-weight:bold")
        bot = QHBoxLayout(); [bot.addWidget(w) for w in (self.btn_run, self.btn_cancel)]; bot.addWidget(self.progress, 1)
        bot.addWidget(self.lbl_status); bot.addWidget(self.lbl_stale); bot.addWidget(self.btn_export)
        c = QWidget(); lc2 = QVBoxLayout(c); lc2.addWidget(split, 1); lc2.addLayout(bot); self.setCentralWidget(c)

    # ------------------------------------------------------------- Einstellungen
    def _load_settings(self):
        s = self.settings
        for sp, k in ((self.sp_warn, "warn"), (self.sp_err, "err"), (self.sp_tt_warn, "ttwarn"), (self.sp_tt_err, "tterr"), (self.sp_contrast, "contrast")):
            v = s.value("th/" + k)
            if v is not None:
                sp.setValue(float(v))
        root = Path(__file__).resolve().parents[3]
        self.ed_white.setText(s.value("whitelist", str(root / "config" / "whitelist.txt")))
        self.ed_out.setText(s.value("outdir", str(Path.home() / "CAD-QM-Ausgabe")))

    def _save_settings(self):
        s = self.settings
        for sp, k in ((self.sp_warn, "warn"), (self.sp_err, "err"), (self.sp_tt_warn, "ttwarn"), (self.sp_tt_err, "tterr"), (self.sp_contrast, "contrast")):
            s.setValue("th/" + k, sp.value())
        s.setValue("whitelist", self.ed_white.text()); s.setValue("outdir", self.ed_out.text())

    def closeEvent(self, e):
        self._save_settings()
        if self.worker and self.worker.isRunning():
            self.worker.cancel(); self.worker.wait(5000)
        super().closeEvent(e)

    def thresholds(self) -> dict:
        o = dict(self.cfg["overlap"])
        o.update(warn_pct=self.sp_warn.value(), error_pct=self.sp_err.value(),
                 text_text_warn_pct=self.sp_tt_warn.value(), text_text_error_pct=self.sp_tt_err.value())
        return o

    def _thresholds_changed(self):
        if self.sp_err.value() < self.sp_warn.value():
            self.sp_err.setValue(self.sp_warn.value())
        if self.sp_tt_err.value() < self.sp_tt_warn.value():
            self.sp_tt_err.setValue(self.sp_tt_warn.value())
        self.refresh()

    def _signature(self):
        return (tuple(self.files), self.cb_overlap.isChecked(), self.cb_spell.isChecked(), self.cb_cons.isChecked(),
                round(self.sp_contrast.value(), 3), self.ed_white.text())

    def _settings_changed(self, *_):
        self._update_state()

    def _update_state(self):
        stale = self.run_signature is not None and self._signature() != self.run_signature
        self.lbl_stale.setText("Einstellungen geändert – neu prüfen" if stale else "")
        self.btn_run.setEnabled(bool(self.files) and not (self.worker and self.worker.isRunning()))
        self.btn_export.setEnabled(bool(self.rows))

    # ------------------------------------------------------------------- Dateien
    def add_paths(self, paths):
        for p in paths:
            p = str(p)
            if p.lower().endswith(".pdf") and p not in self.files:
                self.files.append(p); self.file_list.addItem(os.path.basename(p)); self.file_list.item(self.file_list.count() - 1).setToolTip(p)
        self._update_state()

    def add_files(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "Pläne wählen", self.settings.value("lastdir", ""), "PDF (*.pdf)")
        if fs:
            self.settings.setValue("lastdir", os.path.dirname(fs[0])); self.add_paths(fs)

    def add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Ordner mit Plansatz", self.settings.value("lastdir", ""))
        if d:
            self.settings.setValue("lastdir", d); self.add_paths(sorted(Path(d).glob("*.pdf")))

    def remove_files(self):
        for it in self.file_list.selectedItems():
            self.files.remove(it.toolTip()); self.file_list.takeItem(self.file_list.row(it))
        self._update_state()

    def pick_whitelist(self):
        f, _ = QFileDialog.getSaveFileName(self, "Whitelist-Datei", self.ed_white.text(), "Text (*.txt)", options=QFileDialog.DontConfirmOverwrite)
        if f:
            self.ed_white.setText(f); self._settings_changed()

    def pick_outdir(self):
        d = QFileDialog.getExistingDirectory(self, "Ausgabeordner", self.ed_out.text())
        if d:
            self.ed_out.setText(d)

    # --------------------------------------------------------------------- Pruefen
    def start(self):
        checks = tuple(n for n, c in (("overlap", self.cb_overlap), ("spelling", self.cb_spell), ("consistency", self.cb_cons)) if c.isChecked())
        if not checks:
            QMessageBox.information(self, "CAD-QM", "Bitte mindestens eine Prüfung auswählen."); return
        cfg = copy.deepcopy(self.cfg)
        cfg["overlap"].update(warn_pct=RAW_WARN_FLOOR, text_text_warn_pct=RAW_TT_FLOOR, contrast_min=self.sp_contrast.value())
        self._save_settings()
        wl = [self.ed_white.text()] if self.ed_white.text() else []
        self.worker = Worker(list(self.files), cfg, checks, wl)
        self.worker.progress.connect(self._progress); self.worker.done.connect(self._done); self.worker.failed.connect(self._failed)
        self.run_signature = self._signature()
        self.btn_cancel.setEnabled(True); self.btn_run.setEnabled(False); self.lbl_status.setText("Prüfe …")
        self.worker.start()

    def _progress(self, i, n, msg):
        self.progress.setRange(0, max(n, 1)); self.progress.setValue(i); self.lbl_status.setText(msg)

    def _done(self, res: dict):
        self.raw = res
        self.btn_cancel.setEnabled(False); self.lbl_status.setText("Fertig")
        self.ignored.clear(); self.refresh(); self._update_state()

    def _failed(self, msg):
        self.btn_cancel.setEnabled(False); self.lbl_status.setText(msg); self._update_state()
        if msg != "Abgebrochen":
            QMessageBox.critical(self, "CAD-QM", msg)

    def cancel(self):
        if self.worker:
            self.worker.cancel(); self.lbl_status.setText("Breche ab …")

    # --------------------------------------------------------------------- Befunde
    @staticmethod
    def _key(path, f: Finding):
        return (path, f.type, f.page, round(f.bbox[0]), round(f.bbox[1]), f.text)

    def _all_rows(self) -> list[tuple[str, Finding]]:
        """Schwellen anwenden, Whitelist-Woerter dieser Sitzung entfernen, clustern."""
        o = self.thresholds(); rows = []
        for path, fs in self.raw.items():
            fs = [f for f in apply_thresholds(fs, o) if not (f.type == SPELLING and f.text.lower() in self.session_whitelist)]
            rows += [(path, f) for f in cluster(fs)]
        return rows

    def refresh(self):
        sel_key = None
        cur = self._selected()
        if cur:
            sel_key = self._key(*cur)
        self.rows = self._all_rows()
        ti = self.cmb_type.currentIndex(); types = [None, OVERLAP, SPELLING, CONSISTENCY]
        q = self.ed_search.text().strip().lower()
        shown = [(p, f) for p, f in self.rows
                 if (types[ti] is None or f.type == types[ti]) and (not self.cb_only_err.isChecked() or f.severity == "error")
                 and (not q or q in f"{os.path.basename(p)} {f.text} {f.detail} {f.id}".lower())]
        self.view = shown
        colors = self.cfg["markup"]["colors"]
        self.table.blockSignals(True); self.table.setSortingEnabled(False); self.table.setRowCount(len(shown))
        for r, (path, f) in enumerate(shown):
            ign = self._key(path, f) in self.ignored
            chk = QTableWidgetItem(); chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk.setCheckState(Qt.Unchecked if ign else Qt.Checked); chk.setData(Qt.UserRole, r)
            vals = [f.id, os.path.basename(path), TYPE_NAME[f.type], SEV_NAME[f.severity], f.value if f.type == OVERLAP else None, f.text, f.detail]
            self.table.setItem(r, 0, chk)
            for c, v in enumerate(vals, start=1):
                it = QTableWidgetItem(); it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                it.setData(Qt.DisplayRole, v if v is not None else ""); it.setData(Qt.UserRole, r)
                if c == 3:
                    it.setForeground(QBrush(QColor(*[int(x * 200) for x in colors[f.type]]))); 
                if c == 4:
                    it.setBackground(QBrush(QColor("#ffd6d6") if f.severity == "error" else QColor("#fff3c4")))
                if ign:
                    it.setForeground(QBrush(QColor("#999999")))
                self.table.setItem(r, c, it)
        self.table.setSortingEnabled(True); self.table.blockSignals(False)
        e = sum(1 for _, f in self.rows if f.severity == "error")
        self.lbl_count.setText(f"{len(shown)} von {len(self.rows)} Befunden ({e} Fehler)")
        if sel_key:                                              # Auswahl nach Schwellen-Aenderung moeglichst beibehalten
            for r in range(self.table.rowCount()):
                p, f = self.view[self.table.item(r, 0).data(Qt.UserRole)]
                if self._key(p, f) == sel_key:
                    self.table.selectRow(r); break
        self._update_state()

    def _selected(self):
        r = self.table.currentRow()
        if r < 0 or r >= self.table.rowCount() or not getattr(self, "view", None):
            return None
        idx = self.table.item(r, 0).data(Qt.UserRole)
        return self.view[idx] if idx is not None and idx < len(self.view) else None

    def show_preview(self):
        sel = self._selected()
        if not sel:
            return
        path, f = sel
        try:
            self.lbl_prev.setPixmap(render_preview(path, f.page, f.bbox, self.cfg["markup"]["colors"][f.type]))
        except Exception as e:                                   # noqa: BLE001
            self.lbl_prev.setText(f"Vorschau nicht möglich: {e}")
        self.lbl_info.setText(f"<b>{f.id} – {TYPE_NAME[f.type]}</b> ({SEV_NAME[f.severity]})<br>{os.path.basename(path)}, Seite {f.page + 1}<br>"
                              f"{f.detail}" + (f"<br>Wert: {f.value:g} %" if f.type == OVERLAP else "") + f"<br><i>{f.text}</i>")
        self.btn_white.setEnabled(f.type == SPELLING)

    def _item_changed(self, item):
        if item.column() != 0:
            return
        idx = item.data(Qt.UserRole)
        if idx is None or idx >= len(self.view):
            return
        k = self._key(*self.view[idx])
        (self.ignored.discard if item.checkState() == Qt.Checked else self.ignored.add)(k)

    def toggle_selected(self):
        r = self.table.currentRow()
        if r >= 0:
            it = self.table.item(r, 0); it.setCheckState(Qt.Unchecked if it.checkState() == Qt.Checked else Qt.Checked)

    def add_to_whitelist(self):
        sel = self._selected()
        if not sel or sel[1].type != SPELLING:
            return
        word = sel[1].text.strip()
        path = self.ed_white.text().strip()
        if path:
            try:
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(word + "\n")
            except OSError as e:
                QMessageBox.warning(self, "CAD-QM", f"Whitelist nicht beschreibbar: {e}"); return
        self.session_whitelist.add(word.lower())
        self.refresh()
        self.lbl_status.setText(f"„{word}“ zur Whitelist hinzugefügt")

    # ---------------------------------------------------------------------- Export
    def export(self):
        out = Path(self.ed_out.text().strip() or ".")
        keep = [(p, f) for p, f in self.rows if self._key(p, f) not in self.ignored]
        if not keep:
            QMessageBox.information(self, "CAD-QM", "Keine Befunde zum Exportieren (alle ausgeblendet?)."); return
        try:
            out.mkdir(parents=True, exist_ok=True)
            by_file: dict[str, list[Finding]] = {}
            for p, f in keep:
                by_file.setdefault(p, []).append(f)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            for p in self.files:
                doc = pymupdf.open(p); fs = by_file.get(p, [])
                add_markup(doc, fs, self.cfg); add_summary(doc, fs, self.cfg, Path(p).stem)
                doc.save(out / f"{Path(p).stem}_QM.pdf", garbage=3, deflate=True)
            write_xlsx([(Path(p).stem, f) for p, f in keep], str(out / "QM_Befunde.xlsx"))
        except Exception as e:                                   # noqa: BLE001
            QMessageBox.critical(self, "CAD-QM", f"Export fehlgeschlagen: {e}"); return
        finally:
            QApplication.restoreOverrideCursor()
        self.lbl_status.setText(f"Exportiert nach {out}")
        QMessageBox.information(self, "CAD-QM", f"{len(keep)} Befunde exportiert nach:\n{out}")


def main(argv=None) -> int:
    app = QApplication(sys.argv if argv is None else argv)
    w = MainWindow()
    w.add_paths([a for a in (argv or sys.argv)[1:] if a.lower().endswith(".pdf")])
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
