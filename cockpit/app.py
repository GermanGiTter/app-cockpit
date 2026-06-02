"""App-Cockpit — Übersicht, Git-Status, Befehle kopieren / in PowerShell starten."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import streamlit as st

from cockpit.lib.paths import bundle_root, data_root

ROOT = data_root()
if str(bundle_root()) not in sys.path:
    sys.path.insert(0, str(bundle_root()))

from cockpit.lib.manifest import MANIFEST, filter_apps, load_manifest, playbook_markdown


def sort_apps_by_name(apps: list[dict]) -> list[dict]:
    return sorted(apps, key=lambda a: (a.get("name") or a.get("id") or "").casefold())
from cockpit.lib.status import (
    git_status,
    path_exists,
    pick_primary_command,
    script_for_powershell,
)


@st.cache_data(ttl=30)
def cached_git(path: str) -> dict:
    gs = git_status(path)
    return {
        "is_repo": gs.is_repo,
        "branch": gs.branch,
        "dirty": gs.dirty,
        "ahead": gs.ahead,
        "behind": gs.behind,
        "message": gs.message,
    }


RELEASE_LABELS = {
    "vercel": "Release → Vercel",
    "mac_ios": "Release → Mac (iPhone/iPad)",
    "windows": "Nur Windows",
    "local": "Nur lokal",
    "android_usb": "Android (USB/APK)",
}


def workflow_badge(app: dict) -> str:
    wf = app.get("workflow") or {}
    release = wf.get("release_on", "")
    label = RELEASE_LABELS.get(release, release or "—")
    dev = wf.get("dev_on", "")
    if dev:
        return f"Dev: {dev} · {label}"
    return label


def git_label(data: dict) -> str:
    if data.get("message") and not data.get("is_repo"):
        return data["message"]
    if not data.get("is_repo"):
        return "—"
    parts = [data.get("branch") or "?"]
    if data.get("dirty"):
        parts.append("geändert")
    if data.get("ahead"):
        parts.append(f"↑{data['ahead']}")
    if data.get("behind"):
        parts.append(f"↓{data['behind']}")
    if data.get("dirty") is False and not data.get("ahead") and not data.get("behind"):
        parts.append("sauber")
    return " · ".join(parts)


def open_in_powershell(script: str) -> None:
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoExit",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        cwd=None,
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
    )


def render_overview(apps: list[dict]) -> None:
    st.subheader("Übersicht")
    cols = st.columns(min(len(apps), 4))
    for i, app in enumerate(apps):
        local = app.get("local_path") or ""
        exists = path_exists(local)
        git = cached_git(local) if exists else {}
        with cols[i % len(cols)]:
            st.markdown(f"**{app.get('name', '?')}**")
            st.caption("✅ Ordner" if exists else "❌ Ordner fehlt")
            if exists:
                st.caption(git_label(git))
            wf = app.get("workflow")
            if wf:
                st.caption(workflow_badge(app))


def render_app_detail(app: dict) -> None:
    name = app.get("name", app.get("id", "?"))
    local = app.get("local_path") or ""
    exists = path_exists(local)

    st.header(name)
    st.write(app.get("description", ""))

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Projektordner", "OK" if exists else "fehlt")
    with m2:
        if exists:
            st.metric("Git", git_label(cached_git(local)))
        else:
            st.metric("Git", "—")
    with m3:
        folder = app.get("repo_folder") or Path(local).name if local else "—"
        st.metric("Ordnername", folder)

    if local:
        st.code(local, language=None)
        if app.get("repo_folder"):
            st.caption(f"App-Name ≠ Ordner: Repository heißt {app['repo_folder']}")

    if app.get("github"):
        st.link_button("GitHub öffnen", app["github"])

    wf = app.get("workflow")
    if wf:
        st.subheader("Wohin & wie?")
        st.info(wf.get("summary", ""))
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Entwicklung:**", wf.get("dev_on", "—"))
        with c2:
            rel = wf.get("release_on", "—")
            st.write("**Release:**", RELEASE_LABELS.get(rel, rel))
        steps = wf.get("steps") or []
        if steps:
            st.markdown("**Schritt für Schritt**")
            for i, step in enumerate(steps, start=1):
                if isinstance(step, str):
                    st.markdown(f"{i}. {step}")
                else:
                    st.markdown(f"**{i}. {step.get('title', '')}**")
                    if step.get("detail"):
                        st.write(step["detail"])

    meta = st.columns(3)
    with meta[0]:
        if app.get("stack"):
            st.write("**Stack:**", ", ".join(app["stack"]))
    with meta[1]:
        if app.get("tags"):
            st.write("**Tags:**", ", ".join(app["tags"]))
    with meta[2]:
        if app.get("targets"):
            st.write("**Ziele:**", ", ".join(app["targets"]))

    commands: dict[str, str] = app.get("commands") or {}
    primary = pick_primary_command(commands)

    if primary and exists:
        key, script = primary
        st.subheader("Schnellstart")
        full = script_for_powershell(local, script)
        st.code(full, language="powershell")
        c1, c2 = st.columns(2)
        with c1:
            st.caption(f"Primärer Befehl: `{key}` (Codeblock oben → Kopieren)")
        with c2:
            if st.button(
                "In neuem PowerShell-Fenster starten",
                key=f"run-{app.get('id')}-{key}",
                type="primary",
            ):
                st.session_state[f"confirm-run-{app.get('id')}"] = True
        if st.session_state.get(f"confirm-run-{app.get('id')}"):
            st.warning(
                "Startet einen Befehl auf deinem PC. Nur nutzen, wenn du dem Skript vertraust."
            )
            if st.button("Ja, PowerShell öffnen", key=f"confirm-{app.get('id')}"):
                open_in_powershell(full)
                st.success("PowerShell-Fenster geöffnet.")
                del st.session_state[f"confirm-run-{app.get('id')}"]

    if app.get("prerequisites"):
        with st.expander("Voraussetzungen", expanded=False):
            for line in app["prerequisites"]:
                st.write(f"- {line}")

    if commands:
        st.subheader("Alle Befehle")
        for cmd_key, script in commands.items():
            label = f"`{cmd_key}`" + (" (Standard)" if primary and cmd_key == primary[0] else "")
            st.markdown(label)
            body = script_for_powershell(local, script) if exists and local else script.strip()
            st.code(body, language="powershell")

    if app.get("notes"):
        st.subheader("Hinweise")
        for note in app["notes"]:
            st.write(f"- {note}")


def main() -> None:
    st.set_page_config(page_title="App-Cockpit", page_icon="🧭", layout="wide")
    data = load_manifest()
    apps: list[dict] = sort_apps_by_name(data.get("apps", []))

    st.sidebar.title("App-Cockpit")
    st.sidebar.caption(f"`{MANIFEST}`")
    if st.sidebar.button("Status neu laden"):
        st.cache_data.clear()
        st.rerun()

    all_tags = sorted({t for a in apps for t in a.get("tags", [])})
    all_stacks = sorted({s for a in apps for s in a.get("stack", [])})
    q = st.sidebar.text_input("Suche", "")
    tag_filter = st.sidebar.multiselect("Tags", all_tags)
    stack_filter = st.sidebar.multiselect("Stack", all_stacks)

    filtered = sort_apps_by_name(
        filter_apps(apps, query=q, tags=tag_filter, stacks=stack_filter)
    )

    st.sidebar.divider()
    app_names = [a.get("name", a.get("id", "?")) for a in filtered]
    if not app_names:
        st.sidebar.warning("Keine App passt zum Filter.")
        page = None
    else:
        page = st.sidebar.radio("App", ["Übersicht", *app_names], index=0)

    st.title("App-Cockpit")
    st.caption("Nachschlagebuch und Starter für deine Apps")

    if page == "Übersicht" or page is None:
        render_overview(filtered if filtered else apps)
        st.divider()
        st.info("Links eine App wählen für Details, Schnellstart und alle Befehle.")
        with st.expander("Playbook als Markdown herunterladen"):
            md = playbook_markdown(sort_apps_by_name(filtered if filtered else apps))
            st.download_button(
                "PLAYBOOK.md",
                data=md,
                file_name="PLAYBOOK.md",
                mime="text/markdown",
            )
    else:
        app = next(a for a in filtered if a.get("name") == page)
        render_app_detail(app)

    st.sidebar.divider()
    st.sidebar.markdown(
        "**Pflegen:** `apps.yaml` bearbeiten, dann „Status neu laden“.\n\n"
        "**Start:** `tools\\run-cockpit.ps1`"
    )


if __name__ == "__main__":
    main()
