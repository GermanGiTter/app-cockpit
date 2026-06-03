"""Git-Status-Snapshot (session), statt bei jeder UI-Aktion alle Repos zu scannen."""

from __future__ import annotations

from datetime import datetime

from cockpit.lib.manifest import path_diagnosis
from cockpit.lib.status import GitStatus, git_status, path_exists


def git_status_to_dict(gs: GitStatus) -> dict:
    return {
        "is_repo": gs.is_repo,
        "branch": gs.branch,
        "dirty": gs.dirty,
        "ahead": gs.ahead,
        "behind": gs.behind,
        "message": gs.message,
    }


def empty_git_dict(message: str = "—") -> dict:
    return {
        "is_repo": False,
        "branch": None,
        "dirty": None,
        "ahead": None,
        "behind": None,
        "message": message,
    }


def build_git_snapshot(apps: list[dict]) -> dict[str, dict]:
    """Einmal alle Pfade scannen — nur bei explizitem Refresh aufrufen."""
    snap: dict[str, dict] = {}
    for app in apps:
        local = app.get("local_path") or ""
        ok, _ = path_diagnosis(local)
        if not ok or not local:
            snap[local] = empty_git_dict("Ordner fehlt")
            continue
        snap[local] = git_status_to_dict(git_status(local))
    return snap


def refresh_paths(snapshot: dict[str, dict], paths: list[str]) -> None:
    for path in paths:
        if path and path_exists(path):
            snapshot[path] = git_status_to_dict(git_status(path))


def snapshot_apps_key(apps: list[dict]) -> tuple[str, ...]:
    return tuple(sorted(a.get("id", "") for a in apps))
