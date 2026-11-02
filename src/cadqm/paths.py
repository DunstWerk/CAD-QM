"""Pfade fuer Entwicklung und gebuendelte App (PyInstaller). Konfiguration/Whitelist liegen NEBEN der exe und sind editierbar."""
from __future__ import annotations
import os
import sys
from pathlib import Path


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Ordner der exe (gebuendelt) bzw. Repo-Wurzel (Entwicklung)."""
    return Path(sys.executable).resolve().parent if frozen() else Path(__file__).resolve().parents[2]


def config_dir() -> Path:
    d = app_dir() / "config"
    if d.is_dir():
        return d
    return Path(getattr(sys, "_MEIPASS", app_dir())) / "config"       # gebuendelte Standardkonfiguration als Rueckfall


def user_dir() -> Path:
    d = Path.home() / "CAD-QM"
    d.mkdir(parents=True, exist_ok=True)
    return d


def writable_whitelist() -> Path:
    """Whitelist neben der exe, falls beschreibbar (z. B. entpackter Ordner), sonst im Benutzerordner."""
    p = config_dir() / "whitelist.txt"
    try:
        if p.exists() and os.access(p, os.W_OK):
            return p
        if not p.exists() and os.access(config_dir(), os.W_OK):
            p.write_text("# Projekt-Whitelist: ein Wort pro Zeile\n", encoding="utf-8")
            return p
    except OSError:
        pass
    return user_dir() / "whitelist.txt"
