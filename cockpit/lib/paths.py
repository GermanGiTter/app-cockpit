"""Pfade für Entwicklung vs. PyInstaller-.exe."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def data_root() -> Path:
    """Daten neben der .exe (apps.yaml — vom Nutzer editierbar)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def bundle_root() -> Path:
    """Eingebettete App-Dateien (Streamlit, cockpit-Code)."""
    if is_frozen():
        return Path(sys._MEIPASS)
    return data_root()


def manifest_path() -> Path:
    return data_root() / "apps.yaml"


def cockpit_app_path() -> Path:
    return bundle_root() / "cockpit" / "app.py"
