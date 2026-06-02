"""apps.yaml laden und filtern."""

from __future__ import annotations

import yaml

from cockpit.lib.paths import data_root, manifest_path

ROOT = data_root()
MANIFEST = manifest_path()


def app_sort_key(app: dict) -> str:
    return (app.get("name") or app.get("id") or "").casefold()


def sort_apps(apps: list[dict]) -> list[dict]:
    return sorted(apps, key=app_sort_key)


def load_manifest() -> dict:
    with MANIFEST.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def filter_apps(
    apps: list[dict],
    *,
    query: str = "",
    tags: list[str] | None = None,
    stacks: list[str] | None = None,
) -> list[dict]:
    tags = tags or []
    stacks = stacks or []
    out: list[dict] = []
    for app in apps:
        if tags and not set(tags).issubset(set(app.get("tags", []))):
            continue
        if stacks and not set(stacks).issubset(set(app.get("stack", []))):
            continue
        if query:
            blob = (
                f"{app.get('name', '')} {app.get('id', '')} "
                f"{app.get('description', '')} {app.get('repo_folder', '')}"
            ).lower()
            if query.lower() not in blob:
                continue
        out.append(app)
    return sort_apps(out)


def playbook_markdown(apps: list[dict]) -> str:
    apps = sort_apps(apps)
    lines = ["# App-Playbook\n", f"_Automatisch aus `{MANIFEST.name}`._\n"]
    for app in apps:
        lines.append(f"\n## {app.get('name', app.get('id', '?'))}\n")
        if app.get("description"):
            lines.append(f"{app['description']}\n")
        if app.get("local_path"):
            lines.append(f"- **Pfad:** `{app['local_path']}`\n")
        if app.get("github"):
            lines.append(f"- **GitHub:** {app['github']}\n")
        if app.get("stack"):
            lines.append(f"- **Stack:** {', '.join(app['stack'])}\n")
        if app.get("prerequisites"):
            lines.append("\n### Voraussetzungen\n")
            for p in app["prerequisites"]:
                lines.append(f"- {p}\n")
        commands = app.get("commands") or {}
        if commands:
            lines.append("\n### Befehle\n")
            for key, script in commands.items():
                lines.append(f"\n#### `{key}`\n\n```powershell\n{script.strip()}\n```\n")
        if app.get("notes"):
            lines.append("\n### Hinweise\n")
            for note in app["notes"]:
                lines.append(f"- {note}\n")
    return "".join(lines)
