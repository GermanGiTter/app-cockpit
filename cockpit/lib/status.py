"""Pfad- und Git-Status für App-Ordner (nur lesend)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitStatus:
    is_repo: bool
    branch: str | None = None
    dirty: bool | None = None
    ahead: int | None = None
    behind: int | None = None
    head: str | None = None
    message: str | None = None


def path_exists(path_str: str | None) -> bool:
    if not path_str:
        return False
    return Path(path_str).expanduser().is_dir()


def _run_git(path: Path, *args: str, timeout: float = 8.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def git_status(path_str: str | None) -> GitStatus:
    if not path_str:
        return GitStatus(is_repo=False, message="Kein Pfad")
    root = Path(path_str).expanduser()
    if not root.is_dir():
        return GitStatus(is_repo=False, message="Ordner fehlt")
    if not (root / ".git").exists():
        return GitStatus(is_repo=False, message="Kein Git-Repo")

    branch = _run_git(root, "branch", "--show-current")
    if branch.returncode != 0:
        return GitStatus(is_repo=True, message="Git-Fehler (branch)")

    porcelain = _run_git(root, "status", "--porcelain")
    dirty = bool(porcelain.stdout.strip()) if porcelain.returncode == 0 else None

    upstream = _run_git(root, "rev-parse", "--abbrev-ref", "@{upstream}")
    ahead = behind = None
    if upstream.returncode == 0 and upstream.stdout.strip():
        counts = _run_git(root, "rev-list", "--left-right", "--count", "@{upstream}...HEAD")
        if counts.returncode == 0 and counts.stdout.strip():
            parts = counts.stdout.strip().split()
            if len(parts) == 2:
                behind, ahead = int(parts[0]), int(parts[1])

    head_proc = _run_git(root, "rev-parse", "--short", "HEAD")
    head = head_proc.stdout.strip() if head_proc.returncode == 0 else None

    return GitStatus(
        is_repo=True,
        branch=branch.stdout.strip() or "(detached?)",
        dirty=dirty,
        ahead=ahead,
        behind=behind,
        head=head,
        message=None,
    )


def pick_primary_command(commands: dict[str, str]) -> tuple[str, str] | None:
    if not commands:
        return None
    for key in ("dev", "dev_gui", "dev_ipad", "dev_alt_port", "android", "ios", "web"):
        if key in commands:
            return key, commands[key]
    first = next(iter(commands.items()))
    return first[0], first[1]


def script_for_powershell(local_path: str, script: str) -> str:
    """Ein Block zum Kopieren/Ausführen mit festem Projektordner."""
    lines = [f'Set-Location -LiteralPath "{local_path}"']
    for raw in script.strip().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            lines.append(raw.rstrip())
            continue
        if line.lower().startswith("cd "):
            continue
        lines.append(raw.rstrip())
    return "\n".join(lines)
