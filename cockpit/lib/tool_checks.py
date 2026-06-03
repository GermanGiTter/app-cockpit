"""Werkzeug- und Projekt-Checks (nur lesend, keine Builds)."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

NODE_STACK = frozenset(
    {
        "node",
        "react",
        "vite",
        "capacitor",
        "next",
        "typescript",
        "expo",
        "react-native",
    }
)


@dataclass(frozen=True)
class ToolCheckResult:
    name: str
    ok: bool
    detail: str
    fix_hint: str | None = None


FIX_HINTS: dict[str, str] = {
    "flutter": (
        "Flutter SDK installieren, PATH setzen, neues Terminal öffnen. "
        "Dann im Projekt: flutter pub get — bei iOS/Mac: flutter doctor."
    ),
    "dart": "Wird mit dem Flutter SDK mitgeliefert.",
    "node": (
        "Node.js LTS von https://nodejs.org installieren, "
        "PowerShell/Terminal neu starten, dann: node --version"
    ),
    "npm": (
        "npm kommt mit Node.js. Nach der Installation in einem neuen Fenster: npm -v. "
        "Im Projektordner oft: npm install"
    ),
    "npx": "Wird mit npm mitgeliefert — Node.js neu installieren falls npx fehlt.",
    "expo": "Im Projektordner (Cello): npm install, dann npm start. Kein globales expo-CLI nötig.",
    "python": (
        "Python 64-bit installieren (python.org). "
        "Für dieses Cockpit: tools\\run-cockpit.ps1 oder die EXE."
    ),
    "rustc": "Rust von https://rustup.rs — danach Terminal neu öffnen.",
    "cargo": "Wird mit rustup installiert.",
    "git": "Git for Windows installieren und PATH prüfen.",
    "adb": (
        "Android SDK Platform-Tools — oft über Android Studio. "
        "Gerät per USB, USB-Debugging aktiv."
    ),
}


def _run_version(
    executable: str,
    args: list[str] | None = None,
    *,
    timeout: float = 12.0,
) -> tuple[bool, str]:
    args = args or ["--version"]
    path = shutil.which(executable)
    if not path:
        return False, "Nicht im PATH (Befehl nicht gefunden)"
    try:
        proc = subprocess.run(
            [path, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        text = (proc.stdout or proc.stderr or "").strip()
        line = text.splitlines()[0] if text else f"Exit-Code {proc.returncode}"
        if len(line) > 220:
            line = line[:217] + "…"
        return proc.returncode == 0, line
    except subprocess.TimeoutExpired:
        return False, "Zeitüberschreitung — Befehl hängt"
    except OSError as exc:
        return False, str(exc)


def _check_cmd(name: str, executable: str, args: list[str] | None = None) -> ToolCheckResult:
    ok, detail = _run_version(executable, args)
    return ToolCheckResult(
        name=name,
        ok=ok,
        detail=detail,
        fix_hint=None if ok else FIX_HINTS.get(executable, FIX_HINTS.get(name.lower())),
    )


def system_checks_for_stack(stack: list[str]) -> list[ToolCheckResult]:
    tags = {s.lower() for s in stack}
    out: list[ToolCheckResult] = []
    seen: set[str] = set()

    def add(key: str, name: str, exe: str, args: list[str] | None = None) -> None:
        if key in seen:
            return
        seen.add(key)
        out.append(_check_cmd(name, exe, args))

    if tags & {"flutter", "dart"}:
        add("flutter", "Flutter", "flutter", ["--version"])

    if tags & NODE_STACK:
        add("node", "Node.js", "node")
        add("npm", "npm", "npm")

    # Expo: kein „npx expo --version“ — kann Minuten hängen (npm-Download). Siehe project_checks.

    if tags & {"rust", "tauri"}:
        add("rustc", "Rust (rustc)", "rustc")
        add("cargo", "Cargo", "cargo")
        if "node" not in seen:
            add("node", "Node.js (Tauri)", "node")
        if "npm" not in seen:
            add("npm", "npm (Tauri)", "npm")

    if tags & {"python", "streamlit"}:
        add("python", "Python", "python")
        # py launcher auf Windows
        if not shutil.which("python") and shutil.which("py"):
            ok, detail = _run_version("py", ["-3", "--version"])
            out.append(
                ToolCheckResult(
                    name="Python (py -3)",
                    ok=ok,
                    detail=detail,
                    fix_hint=None if ok else FIX_HINTS["python"],
                )
            )

    if tags & {"android", "kotlin"}:
        add("adb", "ADB (Android)", "adb", ["version"])

    # Git ist für fast alle Apps relevant
    add("git", "Git", "git", ["--version"])

    return out


def _read_json_file(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def expo_project_check(root: Path) -> ToolCheckResult:
    """Expo über node_modules prüfen — schnell, ohne npx."""
    expo_pkg = root / "node_modules" / "expo" / "package.json"
    if expo_pkg.is_file():
        ver = _read_json_file(expo_pkg).get("version", "?")
        return ToolCheckResult(
            name="Expo (Projekt)",
            ok=True,
            detail=f"expo {ver} in node_modules",
            fix_hint="Am PC: npm start · iOS am Mac: npm run ios",
        )

    pkg_path = root / "package.json"
    pkg = _read_json_file(pkg_path) if pkg_path.is_file() else {}
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    expo_dep = deps.get("expo")
    if expo_dep:
        return ToolCheckResult(
            name="Expo (Projekt)",
            ok=False,
            detail=f"expo in package.json ({expo_dep}), fehlt in node_modules",
            fix_hint="Im Projektordner: npm install",
        )

    return ToolCheckResult(
        name="Expo (Projekt)",
        ok=False,
        detail="Kein expo in package.json",
        fix_hint=FIX_HINTS["expo"],
    )


def project_checks(local: str, stack: list[str]) -> list[ToolCheckResult]:
    root = Path(local).expanduser()
    if not root.is_dir():
        return []

    tags = {s.lower() for s in stack}
    out: list[ToolCheckResult] = []

    if tags & {"expo", "react-native"}:
        out.append(expo_project_check(root))

    if tags & NODE_STACK:
        pkg = root / "package.json"
        if not pkg.is_file():
            out.append(
                ToolCheckResult(
                    name="Projekt (npm)",
                    ok=False,
                    detail="package.json fehlt im Ordner",
                    fix_hint="Richtigen local_path prüfen oder Projekt klonen.",
                )
            )
        elif not (root / "node_modules").is_dir():
            out.append(
                ToolCheckResult(
                    name="Abhängigkeiten (npm)",
                    ok=False,
                    detail="node_modules fehlt — npm install wurde noch nicht ausgeführt",
                    fix_hint="Im Projektordner in PowerShell: npm install (oder Befehl „install“ oben).",
                )
            )
        else:
            lock = root / "package-lock.json"
            out.append(
                ToolCheckResult(
                    name="Abhängigkeiten (npm)",
                    ok=True,
                    detail="node_modules vorhanden"
                    + ("" if lock.is_file() else " (kein package-lock.json)"),
                    fix_hint=(
                        None
                        if lock.is_file()
                        else "Bei Problemen: package-lock löschen und npm install erneut."
                    ),
                )
            )

    if tags & {"flutter", "dart"}:
        pub = root / "pubspec.yaml"
        if not pub.is_file():
            out.append(
                ToolCheckResult(
                    name="Projekt (Flutter)",
                    ok=False,
                    detail="pubspec.yaml fehlt",
                    fix_hint="local_path prüfen — Flutter-Projektroot?",
                )
            )
        elif not (root / "pubspec.lock").is_file():
            out.append(
                ToolCheckResult(
                    name="Abhängigkeiten (Flutter)",
                    ok=False,
                    detail="pubspec.lock fehlt — Packages noch nicht geholt",
                    fix_hint="Im Projektordner: flutter pub get",
                )
            )
        else:
            out.append(
                ToolCheckResult(
                    name="Abhängigkeiten (Flutter)",
                    ok=True,
                    detail="pubspec.yaml und pubspec.lock vorhanden",
                )
            )

    if tags & {"rust", "tauri"}:
        if not (root / "src-tauri").is_dir() and not (root / "Cargo.toml").is_file():
            out.append(
                ToolCheckResult(
                    name="Projekt (Tauri)",
                    ok=False,
                    detail="Weder src-tauri noch Cargo.toml im Root — Pfad prüfen",
                    fix_hint="TD-9-Ordner oder Tauri-Root in apps.yaml prüfen.",
                )
            )

    if tags & {"android", "kotlin"}:
        gradle = root / "gradlew.bat"
        if not gradle.is_file() and not (root / "gradlew").is_file():
            out.append(
                ToolCheckResult(
                    name="Projekt (Android)",
                    ok=False,
                    detail="gradlew nicht gefunden",
                    fix_hint="Android-Studio-Projektroot in local_path eintragen.",
                )
            )

    if tags & {"python", "streamlit"}:
        venv_py = root / ".venv" / "Scripts" / "python.exe"
        if venv_py.is_file():
            out.append(
                ToolCheckResult(
                    name="Python (.venv)",
                    ok=True,
                    detail="Virtuelle Umgebung .venv vorhanden",
                    fix_hint="Vor dev: .\\.venv\\Scripts\\Activate.ps1",
                )
            )
        else:
            out.append(
                ToolCheckResult(
                    name="Python (.venv)",
                    ok=False,
                    detail="Kein .venv — Einrichtung noch nicht ausgeführt",
                    fix_hint="Befehl install ausführen (py -3 -m venv .venv, pip install -r requirements.txt).",
                )
            )

    return out


def run_flutter_doctor_summary(*, timeout: float = 90.0) -> ToolCheckResult:
    """Ausführlich — nur auf Knopfdruck (kann ~30–90 s dauern)."""
    path = shutil.which("flutter")
    if not path:
        return ToolCheckResult(
            name="Flutter Doctor",
            ok=False,
            detail="flutter nicht im PATH",
            fix_hint=FIX_HINTS["flutter"],
        )
    try:
        proc = subprocess.run(
            [path, "doctor", "-v"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        text = (proc.stdout or proc.stderr or "").strip()
        markers = ("✗", "[✗]", "!", "missing", "not installed", "Unable to")
        important = [ln for ln in text.splitlines() if any(m in ln for m in markers)]
        if not important:
            important = text.splitlines()[-12:]
        detail = "\n".join(important[:30])
        if len(detail) > 1600:
            detail = detail[:1597] + "…"
        ok = proc.returncode == 0 and "✗" not in text
        return ToolCheckResult(
            name="Flutter Doctor",
            ok=ok,
            detail=detail or f"Exit-Code {proc.returncode}",
            fix_hint=None if ok else "Ausgabe oben beheben, dann erneut doctor. Xcode nur auf dem Mac.",
        )
    except subprocess.TimeoutExpired:
        return ToolCheckResult(
            name="Flutter Doctor",
            ok=False,
            detail="Zeitüberschreitung — doctor läuft sehr lange",
            fix_hint="Im Terminal manuell: flutter doctor -v",
        )
    except OSError as exc:
        return ToolCheckResult(name="Flutter Doctor", ok=False, detail=str(exc), fix_hint=FIX_HINTS["flutter"])


def run_checks_for_app(app: dict) -> list[ToolCheckResult]:
    stack = app.get("stack") or []
    local = app.get("local_path") or ""
    results = system_checks_for_stack(stack)
    if local:
        results.extend(project_checks(local, stack))
    return results
