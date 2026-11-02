# PyInstaller-Spec: onedir, Fenster-Anwendung "CAD-QM"
import os
from PyInstaller.utils.hooks import collect_all

here = os.path.dirname(os.path.abspath(SPECPATH if os.path.isdir(SPECPATH) else os.path.dirname(SPECPATH)))
root = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [(os.path.join(root, "src", "cadqm", "data"), os.path.join("cadqm", "data")),     # Hunspell-Woerterbuch
         (os.path.join(root, "config"), "config")]                                         # Standardkonfiguration (Rueckfall)
binaries, hiddenimports = [], ["cv2", "yaml", "openpyxl", "spylls.hunspell"]
for pkg in ("pymupdf", "shapely", "spylls"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

excludes = ["tkinter", "matplotlib", "pytest", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick",
            "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtSql", "PySide6.QtTest"]

a = Analysis([os.path.join(root, "packaging", "cadqm_gui.py")], pathex=[os.path.join(root, "src")], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, excludes=excludes, noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="CAD-QM", console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="CAD-QM")
