"""Baut die App mit PyInstaller (Windows -> CAD-QM.exe, Linux/Mac -> Binary), testet sie per Selbsttest und zippt den Ordner.

    pip install -e ".[gui]" pyinstaller
    python packaging/build_exe.py
"""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def main() -> int:
    subprocess.check_call([sys.executable, "-m", "PyInstaller", str(ROOT / "packaging" / "cadqm.spec"), "--noconfirm", "--clean",
                           "--distpath", str(DIST), "--workpath", str(ROOT / "build")], cwd=ROOT)
    app = DIST / "CAD-QM"
    shutil.copytree(ROOT / "config", app / "config", dirs_exist_ok=True)               # editierbare Konfiguration + Whitelist neben der exe
    (app / "LIESMICH.txt").write_text(
        "CAD-QM – lokale Planprüfung (läuft komplett offline)\n\n"
        "Start: CAD-QM.exe (Windows) bzw. ./CAD-QM (Linux)\n"
        "Einstellungen/Schwellwerte: in der Oberfläche links; Standardwerte und Plankopf-Beschriftungen: config\\default.yaml\n"
        "Whitelist (Fachwörter): config\\whitelist.txt (ein Wort pro Zeile) oder per Button in der Oberfläche\n"
        "Fehlerprotokoll bei Abstürzen: Benutzerordner\\CAD-QM\\error.log\n"
        "Selbsttest: CAD-QM.exe --selftest-out ergebnis.txt\n", encoding="utf-8")
    exe = app / ("CAD-QM.exe" if platform.system() == "Windows" else "CAD-QM")
    result = ROOT / "build" / "selftest.txt"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    rc = subprocess.call([str(exe), "--selftest-out", str(result)], env=env, cwd=app)
    print(result.read_text(encoding="utf-8") if result.exists() else "(kein Selbsttest-Ergebnis)")
    if rc != 0:
        print("Selbsttest FEHLGESCHLAGEN – kein Zip erstellt", file=sys.stderr)
        return 1
    zip_path = shutil.make_archive(str(DIST / f"CAD-QM-{platform.system().lower()}"), "zip", DIST, "CAD-QM")
    print(f"Fertig: {zip_path} ({Path(zip_path).stat().st_size / 1e6:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
