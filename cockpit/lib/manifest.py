"""apps.yaml laden, filtern, validieren."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml
from yaml.error import YAMLError

from cockpit.lib.paths import data_root, manifest_path

ROOT = data_root()
MANIFEST = manifest_path()

NAV_SHORT: dict[str, str] = {
    "mac_ios": "Mac → iPhone/iPad",
    "vercel": "Vercel",
    "android_usb": "Android USB",
    "windows": "nur Windows",
    "local": "nur lokal",
}

PLAYGROUND_HINT = Path(r"C:\Users\rare\.gemini\antigravity\playground")


def app_sort_key(app: dict) -> str:
    return (app.get("name") or app.get("id") or "").casefold()


def sort_apps(apps: list[dict]) -> list[dict]:
    return sorted(apps, key=app_sort_key)


def nav_label(app: dict) -> str:
    name = app.get("name", app.get("id", "?"))
    short = app.get("nav_short")
    if not short:
        release = (app.get("workflow") or {}).get("release_on", "")
        short = NAV_SHORT.get(release, "")
    return f"{name} — {short}" if short else name


def app_search_blob(app: dict) -> str:
    local = app.get("local_path") or ""
    folder = Path(local).name if local else ""
    parts = [
        app.get("name", ""),
        app.get("id", ""),
        app.get("description", ""),
        app.get("repo_folder", ""),
        folder,
        local,
    ]
    return " ".join(parts).lower()


def path_diagnosis(local_path: str | None) -> tuple[bool, str | None]:
    if not local_path:
        return False, "Kein local_path in apps.yaml eingetragen."
    p = Path(local_path).expanduser()
    if p.is_dir():
        return True, None
    parent = p.parent
    suggested = PLAYGROUND_HINT / p.name if p.name else None
    if suggested and suggested != p:
        return False, (
            f"Ordner fehlt: {p}\n"
            f"Vorschlag: Prüfen ob das Projekt unter {suggested} liegt "
            f"und local_path in apps.yaml anpassen."
        )
    return False, f"Ordner fehlt: {p}"


def format_yaml_error(exc: YAMLError) -> str:
    prob = getattr(exc, "problem", None) or str(exc)
    mark = getattr(exc, "problem_mark", None)
    if mark is not None:
        line = mark.line + 1
        col = mark.column + 1
        hint = (
            "Häufige Ursache: Sonderzeichen wie Backticks (`) in ungequotetem Text — "
            "Text in Anführungszeichen setzen oder Backticks entfernen."
        )
        return f"apps.yaml Zeile {line}, Spalte {col}: {prob}\n\n{hint}"
    return f"apps.yaml konnte nicht gelesen werden: {prob}"


def load_manifest() -> dict:
    data, err = load_manifest_safe()
    if err:
        raise RuntimeError(err)
    return data


def load_manifest_safe() -> tuple[dict | None, str | None]:
    try:
        with MANIFEST.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        return None, f"Datei nicht gefunden: {MANIFEST}"
    except YAMLError as exc:
        return None, format_yaml_error(exc)
    except OSError as exc:
        return None, f"Datei konnte nicht gelesen werden: {exc}"
    if not isinstance(data, dict):
        return None, "apps.yaml: Wurzel muss ein Objekt mit 'apps:' sein."
    if "apps" not in data:
        return None, "apps.yaml: Schlüssel 'apps:' fehlt."
    return data, None


def manifest_file_mtime() -> float | None:
    try:
        return MANIFEST.stat().st_mtime
    except OSError:
        return None


def manifest_mtime_label() -> str:
    mtime = manifest_file_mtime()
    if mtime is None:
        return "—"
    return datetime.fromtimestamp(mtime).strftime("%d.%m.%Y %H:%M")


def manifest_changed_since(session: dict) -> bool:
    """True wenn apps.yaml seit dem letzten Lauf geändert wurde (Datei-Zeitstempel)."""
    mtime = manifest_file_mtime()
    key = "manifest_mtime_seen"
    prev = session.get(key)
    session[key] = mtime
    if prev is None or mtime is None:
        return False
    return mtime != prev


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
        if query and query.lower() not in app_search_blob(app):
            continue
        out.append(app)
    return sort_apps(out)


def resolve_doc_path(app: dict, doc: dict) -> Path | None:
    local = app.get("local_path")
    if not local:
        return None
    rel = doc.get("file") or doc.get("path")
    if not rel:
        return None
    p = Path(local) / rel
    return p if p.is_file() else None


def playbook_markdown(apps: list[dict]) -> str:
    from cockpit.lib.commands import get_command_blocks

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
        if app.get("live_url"):
            lines.append(f"- **Live:** {app['live_url']}\n")
        setup, win, mac = get_command_blocks(app)
        if setup:
            lines.append(f"\n### Erstes Mal\n\n```powershell\n{setup.strip()}\n```\n")
        if win:
            lines.append("\n### Windows-PC\n")
            for key, script in win.items():
                lines.append(f"\n#### {key}\n\n```powershell\n{script.strip()}\n```\n")
        if mac:
            lines.append("\n### Mac\n")
            for key, script in mac.items():
                lines.append(f"\n#### {key}\n\n```bash\n{script.strip()}\n```\n")
        if app.get("notes"):
            lines.append("\n### Hinweise\n")
            for note in app["notes"]:
                lines.append(f"- {note}\n")
    return "".join(lines)
