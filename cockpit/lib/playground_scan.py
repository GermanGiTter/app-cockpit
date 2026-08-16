"""Playground-Ordner scannen — Projekte finden, die noch nicht in apps.yaml stehen."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from cockpit.lib.manifest import PLAYGROUND_HINT

SKIP_DIR_NAMES = frozenset(
    {
        "BACKUP",
        "CURSOR_CHAT",
        "node_modules",
        ".venv",
        ".venv-build",
        "__pycache__",
        ".git",
    }
)

RELEASE_LABELS = {
    "mac_ios": "Mac → iPhone/iPad",
    "vercel": "Vercel (Internet)",
    "android_usb": "Android USB",
    "windows": "Nur Windows",
    "local": "Nur lokal",
}


@dataclass(frozen=True)
class DiscoveredProject:
    folder_name: str
    path: str
    stack: list[str]
    tags: list[str]
    github: str | None
    description: str
    release_on: str
    suggested_id: str
    suggested_name: str


def _registered_paths_and_names(apps: list[dict]) -> tuple[set[str], set[str]]:
    paths: set[str] = set()
    names: set[str] = set()
    for app in apps:
        local = app.get("local_path") or ""
        if local:
            paths.add(str(Path(local).expanduser().resolve()).casefold())
            names.add(Path(local).name.casefold())
        for key in ("id", "repo_folder"):
            val = app.get(key)
            if val:
                names.add(str(val).casefold())
    return paths, names


def _should_skip_dir(path: Path) -> bool:
    name = path.name
    if name in SKIP_DIR_NAMES or name.startswith("."):
        return True
    return False


def _git_remote_url(folder: Path) -> str | None:
    git_dir = folder / ".git"
    if not git_dir.is_dir():
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", str(folder), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        url = (proc.stdout or "").strip()
        return url if proc.returncode == 0 and url else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _readme_summary(folder: Path, *, max_len: int = 200) -> str:
    readme = folder / "README.md"
    if not readme.is_file():
        return f"Projektordner {folder.name} im Playground."
    try:
        lines = readme.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return f"Projektordner {folder.name} im Playground."
    for line in lines:
        text = line.strip().lstrip("#").strip()
        if len(text) > 20 and not text.startswith("|") and not text.startswith("```"):
            if len(text) > max_len:
                return text[: max_len - 1] + "…"
            return text
    return f"Projektordner {folder.name} im Playground."


def _slug_from_folder(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    return slug or "neue-app"


def _title_from_folder(name: str) -> str:
    if name.isupper() and len(name) > 2:
        return name.title().replace("-", " ")
    parts = re.split(r"[-_]+", name)
    return " ".join(p.capitalize() for p in parts if p)


def infer_stack(folder: Path) -> list[str]:
    stack: list[str] = []
    if (folder / "pubspec.yaml").is_file():
        stack.extend(["flutter", "dart"])
    pkg = folder / "package.json"
    if pkg.is_file():
        stack.append("node")
        data = _read_json(pkg)
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        for key, tag in (
            ("next", "next"),
            ("react", "react"),
            ("expo", "expo"),
            ("vite", "vite"),
            ("@capacitor/core", "capacitor"),
            ("react-native", "react-native"),
            ("typescript", "typescript"),
        ):
            if key in deps and tag not in stack:
                stack.append(tag)
    if (folder / "requirements.txt").is_file() or (folder / "pyproject.toml").is_file():
        stack.append("python")
        req = ""
        req_path = folder / "requirements.txt"
        if req_path.is_file():
            try:
                req = req_path.read_text(encoding="utf-8", errors="replace").casefold()
            except OSError:
                pass
        if "streamlit" in req:
            stack.append("streamlit")
        if "customtkinter" in req:
            stack.append("customtkinter")
    if (folder / "Cargo.toml").is_file() or (folder / "src-tauri").is_dir():
        stack.extend(["rust", "tauri"])
    if (folder / "build.gradle").is_file() or (folder / "settings.gradle").is_file():
        stack.extend(["android", "kotlin"])
    elif (folder / "app" / "build.gradle").is_file():
        stack.extend(["android", "kotlin"])
    return stack


def infer_release_on(folder: Path, stack: list[str]) -> str:
    tags = {s.lower() for s in stack}
    if (folder / "vercel.json").is_file():
        return "vercel"
    if tags & {"android", "kotlin"} and not tags & {"flutter", "expo", "react-native"}:
        return "android_usb"
    if tags & {"flutter", "expo", "capacitor", "react-native"}:
        return "mac_ios"
    if tags & {"rust", "tauri"}:
        return "windows"
    if tags & {"streamlit"}:
        return "local"
    if tags & {"python", "customtkinter"}:
        return "windows"
    if tags & {"node", "next"}:
        return "vercel"
    if tags & {"node"}:
        return "local"
    return "local"


def infer_tags(stack: list[str], release_on: str) -> list[str]:
    tags: list[str] = []
    if release_on == "vercel":
        tags.append("web")
    if release_on == "android_usb":
        tags.append("mobile")
    if release_on in ("mac_ios", "android_usb"):
        tags.append("mobile")
    if release_on in ("windows", "local"):
        tags.append("desktop")
    if "tooling" in stack or "streamlit" in stack:
        tags.append("tooling")
    return tags or ["draft"]


def scan_playground_folder(folder: Path) -> DiscoveredProject:
    stack = infer_stack(folder)
    release_on = infer_release_on(folder, stack)
    folder_name = folder.name
    return DiscoveredProject(
        folder_name=folder_name,
        path=str(folder.resolve()),
        stack=stack,
        tags=infer_tags(stack, release_on),
        github=_git_remote_url(folder),
        description=_readme_summary(folder),
        release_on=release_on,
        suggested_id=_slug_from_folder(folder_name),
        suggested_name=_title_from_folder(folder_name),
    )


def find_unregistered_projects(apps: list[dict], playground: Path | None = None) -> list[DiscoveredProject]:
    root = playground or PLAYGROUND_HINT
    if not root.is_dir():
        return []

    reg_paths, reg_names = _registered_paths_and_names(apps)
    found: list[DiscoveredProject] = []

    for child in sorted(root.iterdir(), key=lambda p: p.name.casefold()):
        if not child.is_dir() or _should_skip_dir(child):
            continue
        resolved = str(child.resolve()).casefold()
        if resolved in reg_paths or child.name.casefold() in reg_names:
            continue
        found.append(scan_playground_folder(child))

    return found


def _folder_cd(folder_name: str) -> str:
    return f"cd {folder_name}"


def build_app_dict_from_discovery(d: DiscoveredProject) -> dict:
    """App-Eintrag als dict (zum Anhängen an apps.yaml)."""
    wf_summary = {
        "mac_ios": "Windows entwickeln, Mac baut, iPhone/iPad.",
        "vercel": "Windows testen, Live über Vercel (git push).",
        "android_usb": "Android Studio am PC, USB aufs Handy.",
        "windows": "Nur Windows-PC — entwickeln und starten am selben Rechner.",
        "local": "Nur lokal auf dem PC (Browser oder Skript).",
    }.get(d.release_on, "Anpassen in apps.yaml.")

    entry: dict = {
        "id": d.suggested_id,
        "name": d.suggested_name,
        "status": "draft",
        "description": d.description,
        "stack": d.stack,
        "tags": d.tags,
        "local_path": d.path.replace("/", "\\"),
        "workflow": {
            "dev_on": "windows",
            "release_on": d.release_on,
            "summary": wf_summary,
            "steps": [
                {
                    "title": "Einrichten",
                    "detail": "Befehl install ausführen (siehe unten) — aus README ergänzen.",
                },
                {
                    "title": "Starten",
                    "detail": "Befehl dev — Details in apps.yaml und README im Projektordner anpassen.",
                },
            ],
        },
    }
    if d.github:
        entry["github"] = d.github
    if d.folder_name.casefold() != d.suggested_id.casefold():
        entry["repo_folder"] = d.folder_name

    tags = {s.lower() for s in d.stack}
    install_lines = [_folder_cd(d.folder_name)]
    dev_lines = [_folder_cd(d.folder_name)]

    if tags & {"node"}:
        install_lines += ["npm install"]
        dev_lines += ["npm run dev"]
    elif tags & {"flutter"}:
        install_lines += ["flutter pub get"]
        dev_lines += ["flutter run"]
    elif tags & {"python"}:
        install_lines += [
            "py -3 -m venv .venv",
            ".\\.venv\\Scripts\\Activate.ps1",
            "pip install -r requirements.txt",
        ]
        if (Path(d.path) / "config.example.yaml").is_file():
            install_lines.append("copy config.example.yaml config.yaml")
        if (Path(d.path) / "main.py").is_file():
            dev_lines += [".\\.venv\\Scripts\\Activate.ps1", "python main.py gui"]
        elif (Path(d.path) / "app.py").is_file():
            dev_lines += [".\\.venv\\Scripts\\Activate.ps1", "streamlit run app.py"]
        else:
            dev_lines += [".\\.venv\\Scripts\\Activate.ps1", "# Startbefehl aus README eintragen"]
    else:
        install_lines.append("# Siehe README im Projektordner")
        dev_lines.append("# Startbefehl aus README eintragen")

    entry["commands"] = {
        "install": "\n".join(install_lines) + "\n",
        "dev": "\n".join(dev_lines) + "\n",
    }
    entry["notes"] = [
        "Automatisch aus Playground-Scan übernommen — Befehle und Schritte bitte prüfen.",
        f"Erkanntes Muster: {RELEASE_LABELS.get(d.release_on, d.release_on)}.",
    ]
    return entry


def app_dict_to_yaml_block(app: dict) -> str:
    """Einzelnen App-Block als YAML-Text (zum Anhängen).

    Korrektes Listen-Mapping:
      - id: foo
        name: bar
    (nicht name auf derselben Ebene wie „- id“)
    """
    block = yaml.dump(
        app,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=1000,
    )
    lines = [ln for ln in block.rstrip().splitlines() if ln.strip()]
    if not lines:
        return ""
    first, *rest = lines
    out = [f"  - {first}"]
    out.extend(f"    {line}" for line in rest)
    return "\n".join(out)


def append_app_to_manifest(app: dict) -> tuple[bool, str]:
    """App an apps.yaml anhängen (Format der Datei bleibt weitgehend erhalten)."""
    from cockpit.lib.manifest import MANIFEST, load_manifest_safe

    app_id = app.get("id", "")
    if not app_id:
        return False, "Keine App-ID."

    data, err = load_manifest_safe()
    if err:
        return False, err

    apps = data.get("apps", [])
    if any(a.get("id") == app_id for a in apps):
        return False, f"ID „{app_id}“ ist bereits in apps.yaml."

    if not MANIFEST.is_file():
        return False, f"Datei nicht gefunden: {MANIFEST}"

    content = MANIFEST.read_text(encoding="utf-8")
    block = app_dict_to_yaml_block(app)
    if not content.endswith("\n"):
        content += "\n"
    content += "\n" + block + "\n"
    MANIFEST.write_text(content, encoding="utf-8")
    return True, f"„{app.get('name', app_id)}“ wurde in apps.yaml eingetragen."
