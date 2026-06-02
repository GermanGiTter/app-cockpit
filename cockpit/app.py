"""App-Cockpit — Übersicht, Wegweiser, Git-Status, Befehle."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

from cockpit.lib.paths import bundle_root, data_root

ROOT = data_root()
if str(bundle_root()) not in sys.path:
    sys.path.insert(0, str(bundle_root()))

from cockpit.lib.manifest import MANIFEST, filter_apps, load_manifest, playbook_markdown
from cockpit.lib.status import (
    git_status,
    path_exists,
    pick_primary_command,
    script_for_powershell,
)
from cockpit.lib.workflow_guide import (
    CATEGORIES,
    apps_in_category,
    category_for_app,
    route_lines,
)


def sort_apps_by_name(apps: list[dict]) -> list[dict]:
    return sorted(apps, key=lambda a: (a.get("name") or a.get("id") or "").casefold())


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
    "vercel": "Internet (Vercel)",
    "mac_ios": "Mac → iPhone/iPad",
    "windows": "Nur Windows",
    "local": "Nur lokal",
    "android_usb": "Android-Handy",
}


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


def open_folder(path: str) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606
    else:
        subprocess.Popen(["xdg-open", path])


def render_guide_page(apps: list[dict]) -> None:
    st.header("Wegweiser: Wohin mit welcher App?")
    st.markdown(
        """
**Die wichtigste Regel:** Es gibt nur wenige Muster — nicht jede App funktioniert gleich.

| Frage | Antwort für die meisten Fälle |
|-------|--------------------------------|
| Wo programmiere ich? | Fast immer auf deinem **Windows-PC** (Playground-Ordner) |
| Muss ich Ordner auf USB kopieren? | **Nein** — bei iPhone-Apps und Einkaufsliste: **Git** (push/pull) |
| Wo landet die App fürs Handy? | **iPhone/iPad** → Mac · **Einkaufsliste** → Vercel-URL · **Alles Zu** → USB/Android Studio |
"""
    )

    for cat in CATEGORIES:
        group = sort_apps_by_name(apps_in_category(apps, cat["release_on"]))
        if not group:
            continue
        with st.expander(
            f"{cat['title']} — {', '.join(a.get('name', '?') for a in group)}",
            expanded=False,
        ):
            st.markdown(f"**Kurz:** {cat['short']}")
            t1, t2, t3 = st.columns(3)
            with t1:
                st.markdown("**Entwickeln**")
                st.write(cat["where_dev"])
            with t2:
                st.markdown("**Übertragen**")
                st.write(cat["how_transfer"])
            with t3:
                st.markdown("**Starten / Nutzen**")
                st.write(cat["where_run"])
            st.caption(f"Nicht: {cat['never']}")
            for app in group:
                st.markdown(f"- **{app.get('name')}** → Sidebar anklicken für Befehle")

    st.divider()
    st.markdown("### Merkhilfe")
    st.code(
        "iPhone/iPad-Apps  =  PC + Git  +  Mac\n"
        "Einkaufsliste      =  PC + git push  +  Vercel-URL im Browser\n"
        "Alles Zu           =  PC + Android Studio + USB\n"
        "TD-9, Kurs-Import  =  nur PC\n"
        "App-Cockpit        =  nur PC (dieses Tool)",
        language=None,
    )


def render_app_card(app: dict, *, compact: bool = False) -> None:
    name = app.get("name", "?")
    local = app.get("local_path") or ""
    exists = path_exists(local)
    cat = category_for_app(app)

    st.markdown(f"**{name}**")
    if cat:
        st.caption(cat["short"])
    if exists:
        st.caption(f"Ordner: OK · Git: {git_label(cached_git(local))}")
    else:
        st.caption("Ordner: fehlt")

    if not compact and cat:
        for label, text in route_lines(app):
            st.markdown(f"- {label}: {text}")


def render_overview(apps: list[dict]) -> None:
    st.subheader("Status aller Apps")
    if not apps:
        st.warning("Keine Apps in der Liste (Filter prüfen oder apps.yaml).")
        return

    st.caption("Ordner: OK oder fehlt · Git-Zeile = Stand im Repository")

    by_type: dict[str, list[dict]] = {}
    for app in apps:
        rel = (app.get("workflow") or {}).get("release_on", "other")
        by_type.setdefault(rel, []).append(app)

    for cat in CATEGORIES:
        group = by_type.get(cat["release_on"], [])
        if not group:
            continue
        st.markdown(f"#### {cat['title']}")
        cols = st.columns(min(len(group), 4) or 1)
        for i, app in enumerate(group):
            with cols[i % len(cols)]:
                render_app_card(app, compact=True)

    other = by_type.get("other", [])
    if other:
        st.markdown("#### Sonstige")
        cols = st.columns(min(len(other), 4) or 1)
        for i, app in enumerate(other):
            with cols[i % len(cols)]:
                render_app_card(app, compact=True)


def render_route_banner(app: dict) -> None:
    cat = category_for_app(app)
    if cat:
        st.markdown(f"**{cat['title']}** — {cat['short']}")
    st.markdown("#### Ablauf")
    for label, text in route_lines(app):
        st.markdown(f"**{label}**  \n{text}")
    if cat:
        with st.expander("Was du nicht brauchst"):
            st.write(cat["never"])


def render_app_detail(app: dict) -> None:
    name = app.get("name", app.get("id", "?"))
    local = app.get("local_path") or ""
    exists = path_exists(local)

    st.header(name)
    st.write(app.get("description", ""))

    render_route_banner(app)

    st.divider()
    btn1, btn2, btn3 = st.columns(3)
    with btn1:
        if local and exists and st.button("Ordner öffnen", key=f"folder-{app.get('id')}"):
            open_folder(local)
    with btn2:
        if app.get("github"):
            st.link_button("GitHub", app["github"])
    with btn3:
        rel = (app.get("workflow") or {}).get("release_on", "")
        st.write("**Typ:**", RELEASE_LABELS.get(rel, rel or "—"))

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

    wf = app.get("workflow")
    if wf and wf.get("steps"):
        st.subheader("Schritt für Schritt")
        for i, step in enumerate(wf["steps"], start=1):
            if isinstance(step, str):
                st.markdown(f"{i}. {step}")
            else:
                st.markdown(f"**{i}. {step.get('title', '')}**")
                if step.get("detail"):
                    st.write(step["detail"])

    commands: dict[str, str] = app.get("commands") or {}
    primary = pick_primary_command(commands)
    rel = (wf or {}).get("release_on", "")

    if primary and exists:
        key, script = primary
        where = (
            "Am Windows-PC ausführen"
            if rel in ("mac_ios", "vercel", "android_usb", "windows", "local", "")
            else "Ausführen"
        )
        st.subheader(f"Befehl jetzt ({where})")
        full = script_for_powershell(local, script)
        st.code(full, language="powershell")
        if rel == "mac_ios":
            st.warning(
                "Dieser Befehl ist für den **PC** (Entwicklung/Test). "
                "Fürs iPhone/iPad die Schritte auf dem **Mac** nutzen (nach git pull)."
            )
        elif rel == "vercel" and key == "dev":
            st.caption(
                "dev = nur lokal testen. Live für alle: Befehl deploy (git push → Vercel)."
            )
        if st.button(
            "In neuem PowerShell-Fenster starten",
            key=f"run-{app.get('id')}-{key}",
            type="primary",
        ):
            st.session_state[f"confirm-run-{app.get('id')}"] = True
        if st.session_state.get(f"confirm-run-{app.get('id')}"):
            st.caption("Nur auf dem PC ausführen, wenn du dem Skript vertraust.")
            if st.button("Ja, PowerShell öffnen", key=f"confirm-{app.get('id')}"):
                open_in_powershell(full)
                st.success("PowerShell geöffnet.")
                del st.session_state[f"confirm-run-{app.get('id')}"]

    if app.get("prerequisites"):
        with st.expander("Voraussetzungen"):
            for line in app["prerequisites"]:
                st.write(f"- {line}")

    if commands:
        st.subheader("Alle Befehle (meist Windows-PC)")
        if rel == "mac_ios":
            st.caption("Mac-Befehle: nach git pull auf dem Mac dieselben npm/flutter-Befehle im Projektordner.")
        for cmd_key, script in commands.items():
            label = f"{cmd_key}" + (" ← Standard" if primary and cmd_key == primary[0] else "")
            st.markdown(f"**{label}**")
            body = script_for_powershell(local, script) if exists and local else script.strip()
            st.code(body, language="powershell")

    if app.get("notes"):
        with st.expander("Hinweise"):
            for note in app["notes"]:
                st.write(f"- {note}")


def main() -> None:
    st.set_page_config(page_title="App-Cockpit", layout="wide")
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
    display_apps = filtered if filtered else apps
    nav = ["Wegweiser", "Übersicht", *[a.get("name", a.get("id", "?")) for a in display_apps]]

    if not display_apps and q:
        st.sidebar.warning("Keine App passt zum Filter.")
        page = "Wegweiser"
    else:
        page = st.sidebar.radio("Navigation", nav, key="cockpit_nav")

    if page == "Wegweiser":
        st.title("Wegweiser")
        st.caption("Wohin mit welcher App?")
        render_guide_page(display_apps)
    elif page == "Übersicht":
        st.title("Übersicht")
        st.caption("Ordner- und Git-Status — nach Typ gruppiert")
        render_overview(display_apps)
        with st.expander("Playbook als Markdown herunterladen"):
            md = playbook_markdown(display_apps)
            st.download_button(
                "PLAYBOOK.md",
                data=md,
                file_name="PLAYBOOK.md",
                mime="text/markdown",
            )
    elif page:
        app = next(a for a in display_apps if a.get("name") == page)
        render_app_detail(app)
    else:
        st.title("App-Cockpit")
        st.info("Wähle links **Wegweiser** oder **Übersicht**.")

    st.sidebar.divider()
    st.sidebar.markdown("**Tipp:** Zuerst „Wegweiser“ lesen.")


if __name__ == "__main__":
    main()
