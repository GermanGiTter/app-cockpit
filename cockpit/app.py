"""App-Cockpit — Wegweiser, Schnellreferenz, Übersicht, App-Details."""

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

from cockpit.lib.checklist import items_for_app, session_key
from cockpit.lib.commands import get_command_blocks
from cockpit.lib.manifest import (
    MANIFEST,
    PLAYGROUND_HINT,
    filter_apps,
    load_manifest_safe,
    nav_label,
    path_diagnosis,
    playbook_markdown,
    resolve_doc_path,
    sort_apps,
)
from cockpit.lib.new_app import build_app_yaml
from cockpit.lib.quickref import quickref_markdown
from cockpit.lib.status import git_status, path_exists, pick_primary_command, script_for_powershell
from cockpit.lib.workflow_guide import CATEGORIES, apps_in_category, category_for_app, route_lines

RELEASE_LABELS = {
    "vercel": "Internet (Vercel)",
    "mac_ios": "Mac → iPhone/iPad",
    "windows": "Nur Windows",
    "local": "Nur lokal",
    "android_usb": "Android-Handy",
}

NAV_STATIC = {
    "Wegweiser": "__guide__",
    "Schnellreferenz": "__quickref__",
    "Übersicht": "__overview__",
}


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


def render_git_alerts(app: dict, local: str) -> None:
    if not local or not path_exists(local):
        return
    g = cached_git(local)
    if not g.get("is_repo"):
        return
    if g.get("dirty"):
        rel = (app.get("workflow") or {}).get("release_on", "")
        hint = {
            "mac_ios": "Vor dem Mac: **commit** und **git push**, dann auf dem Mac **git pull**.",
            "vercel": "Vor dem Live-Deploy: **commit** und **git push** (Vercel baut neu).",
        }.get(rel, "Änderungen sichern: **commit** (und ggf. **push**).")
        st.warning(f"**Git: uncommittete Änderungen** in diesem Projekt. {hint}")
    if g.get("behind"):
        st.info(f"**Git: Branch ist {g['behind']} Commit(s) hinter dem Remote.** → `git pull`")


def render_open_issues(apps: list[dict]) -> None:
    missing = []
    dirty = []
    for app in apps:
        local = app.get("local_path") or ""
        ok, _ = path_diagnosis(local)
        if not ok:
            missing.append(app.get("name", "?"))
        elif path_exists(local):
            g = cached_git(local)
            if g.get("dirty"):
                dirty.append(app.get("name", "?"))
    if not missing and not dirty:
        st.success("**Alles in Ordnung** — alle Pfade vorhanden, keine uncommitteten Änderungen.")
        return
    if missing:
        st.error("**Ordner fehlt:** " + ", ".join(missing))
    if dirty:
        st.warning("**Git geändert (uncommitted):** " + ", ".join(dirty))


def render_docs_links(app: dict) -> None:
    docs = app.get("docs") or []
    if not docs:
        return
    st.subheader("Projekt-Dokumentation")
    cols = st.columns(min(len(docs), 3) or 1)
    for i, doc in enumerate(docs):
        label = doc.get("label") or doc.get("file", "Doku")
        path = resolve_doc_path(app, doc)
        with cols[i % len(cols)]:
            if path:
                if st.button(f"{label} öffnen", key=f"doc-{app.get('id')}-{i}"):
                    open_folder(str(path.parent))
                    st.caption(f"Datei: {path.name}")
            else:
                st.caption(f"{label} — Datei im Projektordner nicht gefunden")


def render_checklist(app: dict) -> None:
    items = items_for_app(app)
    if not items:
        return
    st.subheader("Release-Checkliste")
    st.caption("Abhaken nur für diese Sitzung — als Gedächtnisstütze.")
    app_id = app.get("id", "app")
    for item_id, label in items:
        st.checkbox(label, key=session_key(app_id, item_id))


def render_command_block(
    app: dict,
    title: str,
    commands: dict[str, str],
    *,
    shell: str,
    local: str,
    exists: bool,
    primary: tuple[str, str] | None,
) -> None:
    if not commands:
        return
    st.markdown(f"#### {title}")
    for cmd_key, script in commands.items():
        is_primary = primary and cmd_key == primary[0] and title.startswith("Windows")
        label = f"**{cmd_key}**" + (" ← Standard" if is_primary else "")
        st.markdown(label)
        body = script_for_powershell(local, script) if exists and local and shell == "powershell" else script.strip()
        st.code(body, language=shell)


def render_powershell_runner(app: dict, local: str, key: str, script: str) -> None:
    full = script_for_powershell(local, script)
    st.code(full, language="powershell")
    if st.button(
        "In neuem PowerShell-Fenster starten",
        key=f"run-{app.get('id')}-{key}",
        type="primary",
    ):
        st.session_state[f"confirm-run-{app.get('id')}"] = key
    pending = st.session_state.get(f"confirm-run-{app.get('id')}")
    if pending == key:
        st.warning(
            "**Bestätigung:** Startet einen Befehl auf diesem Windows-PC. "
            "Nur ausführen, wenn du dem Skript vertraust."
        )
        if st.button("Ja, PowerShell öffnen", key=f"confirm-ok-{app.get('id')}-{key}"):
            open_in_powershell(full)
            st.success("PowerShell geöffnet.")
            del st.session_state[f"confirm-run-{app.get('id')}"]


def render_guide_page(apps: list[dict]) -> None:
    st.markdown(
        """
**Regel:** Fast alle Apps startest du auf dem **Windows-PC** im Playground-Ordner.
Was danach passiert, hängt vom **Muster** ab (siehe unten).
"""
    )
    for cat in CATEGORIES:
        group = sort_apps(apps_in_category(apps, cat["release_on"]))
        if not group:
            continue
        with st.expander(
            f"{cat['title']} — {', '.join(a.get('name', '?') for a in group)}",
            expanded=cat["release_on"] == "mac_ios",
        ):
            st.info(f"**Kurz:** {cat['short']}")
            t1, t2, t3 = st.columns(3)
            with t1:
                st.markdown("**Entwickeln**")
                st.write(cat["where_dev"])
            with t2:
                st.markdown("**Übertragen**")
                st.write(cat["how_transfer"])
            with t3:
                st.markdown("**Starten**")
                st.write(cat["where_run"])
            st.caption(f"**Nicht nötig:** {cat['never']}")


def render_quickref_page(apps: list[dict]) -> None:
    md = quickref_markdown(apps)
    st.markdown(md)
    st.download_button(
        "Schnellreferenz.md herunterladen",
        data=md,
        file_name="Schnellreferenz.md",
        mime="text/markdown",
    )
    st.caption("Im Browser: Drucken → Als PDF speichern.")


def render_app_card(app: dict) -> None:
    name = app.get("name", "?")
    local = app.get("local_path") or ""
    ok, _ = path_diagnosis(local)
    cat = category_for_app(app)
    st.markdown(f"**{name}**")
    if cat:
        st.caption(cat["short"])
    if ok:
        st.caption(f"✅ Ordner · Git: {git_label(cached_git(local))}")
    else:
        st.caption("❌ Ordner fehlt")


def render_overview(apps: list[dict]) -> None:
    render_open_issues(apps)
    st.divider()
    st.subheader("Status nach Muster")
    st.caption("✅ = Ordner vorhanden · ❌ = Pfad fehlt")
    by_type: dict[str, list[dict]] = {}
    for app in apps:
        rel = (app.get("workflow") or {}).get("release_on", "other")
        by_type.setdefault(rel, []).append(app)
    for cat in CATEGORIES:
        group = by_type.get(cat["release_on"], [])
        if not group:
            continue
        st.markdown(f"##### {cat['title']}")
        cols = st.columns(min(len(group), 4) or 1)
        for i, app in enumerate(sort_apps(group)):
            with cols[i % len(cols)]:
                render_app_card(app)


def render_route_banner(app: dict) -> None:
    cat = category_for_app(app)
    if cat:
        st.success(f"**{cat['title']}** — {cat['short']}")
    st.markdown("#### Dein Ablauf")
    for label, text in route_lines(app):
        st.markdown(f"**{label}**  \n{text}")


def render_app_detail(app: dict) -> None:
    name = app.get("name", app.get("id", "?"))
    local = app.get("local_path") or ""
    ok, path_msg = path_diagnosis(local)

    st.header(name)
    st.write(app.get("description", ""))
    render_route_banner(app)

    if not ok and path_msg:
        st.error(path_msg)

    if app.get("live_url"):
        st.link_button("Live-App öffnen (Vercel)", app["live_url"])

    render_git_alerts(app, local if ok else "")

    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        if ok and local and st.button("Ordner öffnen", key=f"folder-{app.get('id')}"):
            open_folder(local)
    with c2:
        if app.get("github"):
            st.link_button("GitHub", app["github"])
    with c3:
        rel = (app.get("workflow") or {}).get("release_on", "")
        st.write("**Typ:**", RELEASE_LABELS.get(rel, rel or "—"))

    render_checklist(app)

    wf = app.get("workflow")
    if wf and wf.get("steps"):
        with st.expander("Schritt für Schritt (Details)", expanded=False):
            for i, step in enumerate(wf["steps"], start=1):
                if isinstance(step, str):
                    st.markdown(f"{i}. {step}")
                else:
                    st.markdown(f"**{i}. {step.get('title', '')}**")
                    if step.get("detail"):
                        st.write(step["detail"])

    setup, windows, mac = get_command_blocks(app)
    primary = pick_primary_command(windows) or pick_primary_command(app.get("commands") or {})
    rel = (wf or {}).get("release_on", "")

    if setup:
        st.subheader("Erstes Mal einrichten")
        st.caption("Einmalig auf einem neuen Rechner / frischen Klon.")
        body = script_for_powershell(local, setup) if ok and local else setup.strip()
        st.code(body, language="powershell")

    if windows:
        st.subheader("Befehle am Windows-PC")
        if rel == "mac_ios":
            st.info("**Hier entwickeln und testen.** Fürs Gerät: Abschnitt **Mac** unten.")
        elif rel == "vercel":
            st.info("**dev** = lokal testen. **deploy** / push = Live auf Vercel.")
        if primary and ok:
            st.markdown("##### Schnellstart")
            render_powershell_runner(app, local, primary[0], windows[primary[0]])
        render_command_block(
            app, "Alle (Windows)", windows, shell="powershell", local=local, exists=ok, primary=primary
        )

    if mac:
        st.subheader("Befehle auf dem Mac")
        st.info("Nach **git pull** im Projektordner auf dem Mac ausführen (Terminal).")
        render_command_block(
            app, "Mac", mac, shell="bash", local=local, exists=ok, primary=None
        )

    render_docs_links(app)

    if app.get("prerequisites"):
        with st.expander("Voraussetzungen"):
            for line in app["prerequisites"]:
                st.write(f"- {line}")
    if app.get("notes"):
        with st.expander("Hinweise"):
            for note in app["notes"]:
                st.write(f"- {note}")


def render_new_app_form() -> None:
    with st.sidebar.expander("Neue App (YAML-Vorlage)"):
        app_id = st.text_input("ID (klein, z.B. meine-app)", key="new_id")
        name = st.text_input("Anzeigename", key="new_name")
        desc = st.text_area("Beschreibung", key="new_desc", height=68)
        local = st.text_input("local_path", value=str(PLAYGROUND_HINT) + "\\", key="new_path")
        github = st.text_input("GitHub-URL (optional)", key="new_gh")
        repo_folder = st.text_input("Ordnername im Repo (optional)", key="new_folder")
        release = st.selectbox(
            "Muster",
            ["mac_ios", "vercel", "android_usb", "windows", "local"],
            format_func=lambda x: RELEASE_LABELS.get(x, x),
            key="new_release",
        )
        if st.button("YAML erzeugen"):
            if not app_id or not name:
                st.warning("ID und Name sind Pflicht.")
            else:
                yaml_block = build_app_yaml(
                    app_id=app_id.strip(),
                    name=name.strip(),
                    description=desc.strip() or "Beschreibung ergänzen",
                    local_path=local.strip(),
                    release_on=release,
                    github=github.strip(),
                    repo_folder=repo_folder.strip(),
                )
                st.code(yaml_block, language="yaml")
                st.caption("Block ans Ende von apps.yaml unter apps: einfügen.")


def build_nav(apps: list[dict]) -> tuple[list[str], dict[str, str]]:
    labels = list(NAV_STATIC.keys())
    label_to_id = dict(NAV_STATIC)
    for app in apps:
        label = nav_label(app)
        labels.append(label)
        label_to_id[label] = app.get("id", "")
    return labels, label_to_id


def main() -> None:
    st.set_page_config(page_title="App-Cockpit", layout="wide")

    if "cockpit_nav" not in st.session_state:
        st.session_state.cockpit_nav = "Wegweiser"

    data, yaml_err = load_manifest_safe()
    st.sidebar.title("App-Cockpit")
    st.sidebar.caption(f"`{MANIFEST}`")

    if yaml_err:
        st.error(yaml_err)
        st.stop()

    apps = sort_apps(data.get("apps", []))

    if st.sidebar.button("Status neu laden"):
        st.cache_data.clear()
        st.rerun()

    all_tags = sorted({t for a in apps for t in a.get("tags", [])})
    all_stacks = sorted({s for a in apps for s in a.get("stack", [])})
    q = st.sidebar.text_input("Suche (Name, Ordner, Pfad)", "")
    tag_filter = st.sidebar.multiselect("Tags", all_tags)
    stack_filter = st.sidebar.multiselect("Stack", all_stacks)

    display_apps = sort_apps(filter_apps(apps, query=q, tags=tag_filter, stacks=stack_filter))

    nav_labels, label_to_id = build_nav(display_apps)
    if not display_apps and q:
        st.sidebar.warning("Keine App passt zum Filter.")
        page_label = "Wegweiser"
    else:
        page_label = st.sidebar.radio("Navigation", nav_labels, key="cockpit_nav")

    render_new_app_form()

    page_id = label_to_id.get(page_label, "")

    if page_id == "__guide__":
        st.title("Wegweiser")
        render_guide_page(display_apps if display_apps else apps)
    elif page_id == "__quickref__":
        st.title("Schnellreferenz")
        render_quickref_page(display_apps if display_apps else apps)
    elif page_id == "__overview__":
        st.title("Übersicht")
        render_overview(display_apps if display_apps else apps)
        with st.expander("Playbook.md"):
            md = playbook_markdown(display_apps if display_apps else apps)
            st.download_button("PLAYBOOK.md", data=md, file_name="PLAYBOOK.md", mime="text/markdown")
    elif page_id:
        app = next(a for a in display_apps if a.get("id") == page_id)
        render_app_detail(app)

    st.sidebar.divider()
    st.sidebar.caption("Start: Wegweiser · Druck: Schnellreferenz")


if __name__ == "__main__":
    main()
