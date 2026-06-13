"""Erkannte Updates — Git, apps.yaml, neue Playground-Ordner."""

from __future__ import annotations

from dataclasses import dataclass

from cockpit.lib.manifest import path_diagnosis
from cockpit.lib.playground_scan import DiscoveredProject, find_unregistered_projects
from cockpit.lib.status import path_exists


@dataclass(frozen=True)
class CockpitUpdate:
    kind: str
    app_id: str
    app_name: str
    local_path: str
    title: str
    detail: str
    hint: str


def ensure_git_baseline(apps: list[dict], snapshot: dict[str, dict], session: dict) -> None:
    """Nach erstem Git-Snapshot: Referenz-Commits merken (für „Projekt geändert“)."""
    baseline: dict[str, str] = session.setdefault("git_heads_baseline", {})
    if baseline:
        return
    for app in apps:
        local = app.get("local_path") or ""
        head = snapshot.get(local, {}).get("head")
        if head:
            baseline[local] = head


def mark_project_seen(app: dict, snapshot: dict[str, dict], session: dict) -> None:
    local = app.get("local_path") or ""
    head = snapshot.get(local, {}).get("head")
    if local and head:
        session.setdefault("git_heads_baseline", {})[local] = head
    dismissed: set[str] = session.setdefault("updates_dismissed_behind", set())
    dismissed.add(app.get("id", ""))


def mark_all_projects_seen(apps: list[dict], snapshot: dict[str, dict], session: dict) -> None:
    baseline = session.setdefault("git_heads_baseline", {})
    dismissed: set[str] = session.setdefault("updates_dismissed_behind", set())
    for app in apps:
        local = app.get("local_path") or ""
        head = snapshot.get(local, {}).get("head")
        if local and head:
            baseline[local] = head
        dismissed.add(app.get("id", ""))


def collect_cockpit_updates(
    apps: list[dict],
    snapshot: dict[str, dict],
    session: dict,
    *,
    manifest_changed: bool,
    discovered: list[DiscoveredProject] | None = None,
) -> list[CockpitUpdate]:
    discovered = discovered if discovered is not None else find_unregistered_projects(apps)
    baseline: dict[str, str] = session.get("git_heads_baseline", {})
    dismissed_behind: set[str] = session.get("updates_dismissed_behind", set())
    out: list[CockpitUpdate] = []

    if manifest_changed:
        out.append(
            CockpitUpdate(
                kind="yaml_changed",
                app_id="",
                app_name="apps.yaml",
                local_path="",
                title="Register-Datei wurde geändert",
                detail="apps.yaml wurde auf der Festplatte bearbeitet (Zeitstempel neu).",
                hint="Navigation und Befehle sind bereits neu geladen. Inhalt prüfen: Sidebar → Register-Stand.",
            )
        )

    for app in apps:
        app_id = app.get("id", "")
        name = app.get("name", app_id)
        local = app.get("local_path") or ""
        ok, _ = path_diagnosis(local)
        if not ok or not path_exists(local):
            continue
        g = snapshot.get(local, {})
        if not g.get("is_repo"):
            continue

        behind = g.get("behind") or 0
        if behind > 0 and app_id not in dismissed_behind:
            out.append(
                CockpitUpdate(
                    kind="remote_behind",
                    app_id=app_id,
                    app_name=name,
                    local_path=local,
                    title=f"Update auf GitHub ({behind} Commit(s))",
                    detail=f"**{name}** liegt hinter dem Remote — zuerst `git pull`.",
                    hint="Danach: Befehle/Merksätze in apps.yaml prüfen, Werkzeuge erneut prüfen.",
                )
            )

        head = g.get("head")
        if head and local in baseline and baseline[local] != head:
            out.append(
                CockpitUpdate(
                    kind="local_changed",
                    app_id=app_id,
                    app_name=name,
                    local_path=local,
                    title="Projekt-Stand hat sich geändert",
                    detail=(
                        f"**{name}:** neuer Git-Stand `{head}` "
                        f"(vorher `{baseline[local]}`)."
                    ),
                    hint="README/Befehle geändert? → App-Detail → Merksätze & apps.yaml anpassen.",
                )
            )

    for d in discovered:
        out.append(
            CockpitUpdate(
                kind="new_folder",
                app_id=d.suggested_id,
                app_name=d.suggested_name,
                local_path=d.path,
                title="Neuer Projektordner im Playground",
                detail=f"**{d.suggested_name}** (`{d.folder_name}`) fehlt in apps.yaml.",
                hint="Unten „In apps.yaml übernehmen“ oder apps.yaml manuell ergänzen.",
            )
        )

    return out
