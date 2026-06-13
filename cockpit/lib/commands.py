"""Befehlsblöcke: Setup / Windows / Mac (mit Fallback auf legacy commands)."""

from __future__ import annotations

from datetime import datetime

from cockpit.lib.status import pick_primary_command

_SETUP_KEYS = frozenset({"install", "setup", "first_run"})


def get_command_blocks(app: dict) -> tuple[str | None, dict[str, str], dict[str, str]]:
    mac: dict[str, str] = dict(app.get("commands_mac") or {})
    if "commands_setup" in app or "commands_windows" in app:
        setup = app.get("commands_setup")
        windows = dict(app.get("commands_windows") or {})
        if isinstance(setup, dict):
            setup = "\n".join(f"# {k}\n{v.strip()}" for k, v in setup.items())
        return (setup.strip() if setup else None, windows, mac)

    legacy = app.get("commands") or {}
    if not legacy:
        return None, {}, mac

    setup_parts: list[str] = []
    win: dict[str, str] = {}
    for key, script in legacy.items():
        if key in _SETUP_KEYS:
            setup_parts.append(script.strip())
        else:
            win[key] = script
    combined_setup = "\n\n".join(setup_parts) if setup_parts else None
    return combined_setup, win, mac


def script_has_commands(script: str) -> bool:
    """True wenn mindestens eine ausführbare Zeile (nicht nur Kommentar)."""
    for raw in script.strip().splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            return True
    return False


def get_launch_command(app: dict) -> tuple[str, str] | None:
    """Primärer Start-Befehl (dev o. ä.) aus Windows-/Legacy-Commands."""
    _setup, windows, _mac = get_command_blocks(app)
    legacy = app.get("commands") or {}
    for block in (windows, legacy):
        primary = pick_primary_command(block)
        if primary and script_has_commands(primary[1]):
            return primary
    return None
