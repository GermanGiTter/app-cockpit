"""
Einstiegspunkt für die Windows-.exe (PyInstaller).

Doppelklick startet Streamlit und öffnet den Browser.
`apps.yaml` liegt im gleichen Ordner wie die .exe und kann dort bearbeitet werden.
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
import time
import webbrowser
from pathlib import Path

from cockpit.lib.paths import bundle_root, cockpit_app_path, data_root, is_frozen, manifest_path


def _import_cockpit_libs() -> None:
    """Alle Lib-Module laden, damit PyInstaller sie in die EXE packt."""
    import cockpit.lib.git_batch  # noqa: F401
    import cockpit.lib.git_snapshot  # noqa: F401
    import cockpit.lib.tool_checks  # noqa: F401
    import cockpit.lib.app_memory  # noqa: F401
    import cockpit.lib.playground_scan  # noqa: F401
    import cockpit.lib.updates  # noqa: F401
    import cockpit.lib.checklist  # noqa: F401
    import cockpit.lib.commands  # noqa: F401
    import cockpit.lib.manifest  # noqa: F401
    import cockpit.lib.new_app  # noqa: F401
    import cockpit.lib.quickref  # noqa: F401
    import cockpit.lib.status  # noqa: F401
    import cockpit.lib.workflow_guide  # noqa: F401


def _setup_paths() -> None:
    root = bundle_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _ensure_apps_yaml() -> None:
    target = manifest_path()
    if target.exists():
        return
    bundled = bundle_root() / "apps.yaml"
    if bundled.is_file():
        shutil.copy2(bundled, target)


def _ensure_streamlit_config() -> None:
    dest_dir = data_root() / ".streamlit"
    dest = dest_dir / "config.toml"
    if dest.exists():
        return
    bundled = bundle_root() / ".streamlit" / "config.toml"
    if bundled.is_file():
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled, dest)


def _open_browser(port: str) -> None:
    time.sleep(2.5)
    webbrowser.open(f"http://127.0.0.1:{port}")


def main() -> None:
    _setup_paths()
    _import_cockpit_libs()
    os.chdir(data_root())
    _ensure_apps_yaml()
    _ensure_streamlit_config()

    app_py = cockpit_app_path()
    if not app_py.is_file():
        print(f"Fehler: cockpit/app.py nicht gefunden: {app_py}", file=sys.stderr)
        sys.exit(1)

    port = os.environ.get("APP_COCKPIT_PORT", "8501")

    os.environ.setdefault("STREAMLIT_GLOBAL_DEVELOPMENT_MODE", "false")
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

    if is_frozen():
        threading.Thread(target=_open_browser, args=(port,), daemon=True).start()

    sys.argv = [
        "streamlit",
        "run",
        str(app_py),
        f"--server.port={port}",
        "--server.address=127.0.0.1",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
    ]
    if is_frozen():
        sys.argv.append("--server.runOnSave=false")

    from streamlit.web import cli as stcli

    sys.exit(stcli.main())


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    try:
        main()
    except Exception as exc:
        log = data_root() / "app-cockpit-error.log"
        log.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        raise
