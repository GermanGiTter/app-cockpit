"""Befehlsblöcke: Setup / Windows / Mac (mit Fallback auf legacy commands)."""

from __future__ import annotations

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
