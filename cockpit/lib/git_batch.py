"""Batch commit/push für mehrere Projektordner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cockpit.lib.manifest import path_diagnosis
from cockpit.lib.status import git_status, path_exists


@dataclass
class DirtyProject:
    app_id: str
    name: str
    local_path: str
    branch: str | None
    ahead: int | None


@dataclass
class BatchStepResult:
    action: str
    ok: bool
    detail: str


@dataclass
class BatchProjectResult:
    name: str
    path: str
    steps: list[BatchStepResult]
    success: bool


def find_dirty_projects(apps: list[dict]) -> list[DirtyProject]:
    out: list[DirtyProject] = []
    for app in apps:
        local = app.get("local_path") or ""
        ok, _ = path_diagnosis(local)
        if not ok or not path_exists(local):
            continue
        gs = git_status(local)
        if not gs.is_repo or not gs.dirty:
            continue
        out.append(
            DirtyProject(
                app_id=app.get("id", ""),
                name=app.get("name", app.get("id", "?")),
                local_path=local,
                branch=gs.branch,
                ahead=gs.ahead,
            )
        )
    return out


def _run_git(path: Path, *args: str, timeout: float = 120.0) -> tuple[int, str, str]:
    import subprocess

    proc = subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    combined = "\n".join(x for x in (out, err) if x)
    return proc.returncode, combined, err or out


def run_batch(
    projects: list[DirtyProject],
    *,
    message: str,
    do_commit: bool,
    do_push: bool,
) -> list[BatchProjectResult]:
    results: list[BatchProjectResult] = []
    msg = message.strip()

    for proj in projects:
        root = Path(proj.local_path).expanduser()
        steps: list[BatchStepResult] = []
        ok = True

        if do_commit:
            if not msg:
                steps.append(BatchStepResult("commit", False, "Keine Commit-Nachricht."))
                ok = False
            else:
                code, detail, _ = _run_git(root, "add", "-A")
                if code != 0:
                    steps.append(BatchStepResult("git add", False, detail))
                    ok = False
                else:
                    code, detail, _ = _run_git(root, "commit", "-m", msg)
                    if code != 0:
                        steps.append(BatchStepResult("commit", False, detail))
                        ok = False
                    else:
                        steps.append(BatchStepResult("commit", True, detail or "OK"))

        if do_push and ok:
            gs = git_status(str(root))
            if gs.dirty and not do_commit:
                steps.append(
                    BatchStepResult(
                        "push",
                        False,
                        "Noch uncommittete Änderungen — zuerst Commit ausführen.",
                    )
                )
                ok = False
            else:
                code, detail, _ = _run_git(root, "push", timeout=180.0)
                if code != 0:
                    steps.append(BatchStepResult("push", False, detail))
                    ok = False
                else:
                    steps.append(BatchStepResult("push", True, detail or "OK"))

        if not do_commit and not do_push:
            steps.append(BatchStepResult("—", False, "Keine Aktion gewählt."))
            ok = False

        results.append(
            BatchProjectResult(
                name=proj.name,
                path=str(root),
                steps=steps,
                success=ok,
            )
        )
    return results


def preview_lines(
    projects: list[DirtyProject],
    *,
    message: str,
    do_commit: bool,
    do_push: bool,
) -> list[str]:
    lines: list[str] = []
    for p in projects:
        parts = [f"[{p.name}] {p.local_path}"]
        if do_commit:
            parts.append(f'git add -A && git commit -m "{message.strip()}"')
        if do_push:
            parts.append("git push")
        lines.append(" → ".join(parts))
    return lines
