"""App-Cockpit — Wegweiser, Schnellreferenz, Übersicht, App-Details."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# PyInstaller: Streamlit lädt diese Datei separat — Pfad zur gebündelten App setzen
if getattr(sys, "frozen", False):
    _meipass = getattr(sys, "_MEIPASS", "")
    if _meipass and _meipass not in sys.path:
        sys.path.insert(0, _meipass)

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
from cockpit.lib.git_batch import (
    find_dirty_projects,
    preview_lines,
    run_batch,
)
from cockpit.lib.git_snapshot import (
    build_git_snapshot,
    empty_git_dict,
    git_status_to_dict,
    refresh_paths,
    snapshot_apps_key,
)
from cockpit.lib.status import git_status, path_exists, pick_primary_command, script_for_powershell
from cockpit.lib.app_memory import (
    all_apps_memory_markdown,
    command_legend_for_app,
    memory_bullets,
    memory_markdown_for_app,
    primary_action_hint,
    troubleshooting_for_app,
    when_lost,
)
from cockpit.lib.tool_checks import ToolCheckResult, run_checks_for_app, run_flutter_doctor_summary
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
    "Merksätze": "__memory__",
    "Schnellreferenz": "__quickref__",
    "Übersicht": "__overview__",
}


def _git_snapshot() -> dict[str, dict]:
    return st.session_state.setdefault("git_snapshot", {})


def full_git_snapshot_ready() -> bool:
    return bool(st.session_state.get("git_snapshot_all"))


def load_full_git_snapshot(apps: list[dict]) -> dict[str, dict]:
    snap = build_git_snapshot(apps)
    st.session_state["git_snapshot"] = snap
    st.session_state["git_snapshot_all"] = True
    st.session_state["git_snapshot_ver"] = snapshot_apps_key(apps)
    st.session_state["git_snapshot_at"] = datetime.now().strftime("%H:%M:%S")
    return snap


def clear_git_snapshot() -> None:
    for key in (
        "git_snapshot",
        "git_snapshot_all",
        "git_snapshot_ver",
        "git_snapshot_at",
        "overview_git_auto_attempted",
    ):
        st.session_state.pop(key, None)


def clear_tool_check_cache() -> None:
    drop = [
        k
        for k in st.session_state
        if k.startswith("tool_checks_")
        or k.startswith("tool_auto_")
        or k.startswith("flutter_doctor_")
    ]
    for key in drop:
        st.session_state.pop(key, None)


def _tool_cache_key(app_id: str) -> str:
    return f"tool_checks_{app_id}"


def _run_tool_checks(app: dict) -> list[ToolCheckResult]:
    return run_checks_for_app(app)


def render_tool_diagnostics(app: dict, *, path_ok: bool) -> None:
    """PATH/Versionen und typische Projekt-Probleme (npm install, pub get, …)."""
    if not path_ok:
        return
    app_id = app.get("id", "app")
    cache_key = _tool_cache_key(app_id)
    auto_key = f"tool_auto_{app_id}"

    if cache_key not in st.session_state:
        if not st.session_state.get(auto_key):
            st.session_state[auto_key] = True
            with st.spinner("Werkzeuge und Projekt werden geprüft …"):
                st.session_state[cache_key] = _run_tool_checks(app)
        else:
            if st.button("Werkzeuge & Projekt prüfen", key=f"tool-run-{app_id}", type="primary"):
                with st.spinner("Prüfung läuft …"):
                    st.session_state[cache_key] = _run_tool_checks(app)
            st.caption(
                "Prüft z. B. ob **node**, **npm**, **flutter** im PATH sind "
                "und ob **node_modules** / **pubspec.lock** fehlen."
            )
            return

    if st.button("Werkzeuge erneut prüfen", key=f"tool-refresh-{app_id}"):
        with st.spinner("Prüfung läuft …"):
            st.session_state[cache_key] = _run_tool_checks(app)

    results: list[ToolCheckResult] = st.session_state.get(cache_key, [])
    problems = [r for r in results if not r.ok]

    st.subheader("Umgebung & Werkzeuge")
    if not results:
        st.caption("Keine automatischen Checks für diesen Stack definiert.")
        return
    if not problems:
        st.success("Keine offensichtlichen Probleme bei Werkzeugen und Projekt-Grundlagen.")
    else:
        st.warning(f"**{len(problems)} Hinweis(e)** — bitte vor dem Schnellstart beheben.")

    for r in results:
        if r.ok:
            st.caption(f"✅ **{r.name}:** {r.detail}")
        else:
            st.error(f"**{r.name}:** {r.detail}")
            if r.fix_hint:
                st.caption(f"→ {r.fix_hint}")

    stack = {s.lower() for s in (app.get("stack") or [])}
    if stack & {"flutter", "dart"}:
        if st.button("Flutter Doctor ausführen (langsam)", key=f"flutter-doc-{app_id}"):
            with st.spinner("flutter doctor -v läuft …"):
                st.session_state[f"flutter_doctor_{app_id}"] = run_flutter_doctor_summary()
        doc = st.session_state.get(f"flutter_doctor_{app_id}")
        if doc:
            if doc.ok:
                st.success("Flutter Doctor: keine kritischen ✗ in der Ausgabe.")
            else:
                st.warning("Flutter Doctor: Hinweise gefunden.")
            st.code(doc.detail, language=None)
            if doc.fix_hint:
                st.caption(f"→ {doc.fix_hint}")


def render_troubleshooting(app: dict) -> None:
    tips = troubleshooting_for_app(app)
    if not tips:
        return
    with st.expander("Typische Probleme & Fehlerbehebung", expanded=False):
        st.caption("Häufige Stolpersteine — ohne die vollen Build-Logs zu lesen.")
        for title, fix in tips:
            st.markdown(f"**{title}**")
            st.write(fix)


def render_app_memory_hub(app: dict) -> None:
    wf = app.get("workflow") or {}
    cat = category_for_app(app)

    with st.container(border=True):
        st.subheader("Was war das nochmal?")
        st.markdown(wf.get("summary") or app.get("description", ""))
        st.info(when_lost(app))

        pa = primary_action_hint(app)
        if pa:
            st.markdown(f"**Dein Standard-Schritt:** {pa[0]} — {pa[1]}")

        st.markdown("#### Ablauf in drei Schritten")
        for label, text in route_lines(app):
            st.markdown(f"**{label}** — {text}")

        if cat:
            st.markdown(f"**Muster:** {cat['title']}")
            st.caption(f"Nicht nötig / falsch: {cat['never']}")

        st.markdown("#### Merken")
        for bullet in memory_bullets(app):
            st.markdown(f"- {bullet}")

        local = app.get("local_path") or ""
        if local:
            st.text_input("Projektordner (Pfad)", value=local, disabled=True, key=f"path-show-{app.get('id')}")
        if app.get("repo_folder"):
            st.caption(f"Repo-Ordnername: **{app['repo_folder']}** (Pfad kann anders heißen)")
        if app.get("stack"):
            st.caption("Stack: " + ", ".join(app["stack"]))

        legend = command_legend_for_app(app)
        if legend:
            with st.expander("Was bedeuten die Befehle? (Legende)", expanded=False):
                for key, label, when in legend:
                    st.markdown(f"- **`{key}`** — **{label}:** {when}")

        st.download_button(
            "Diese App als Merksatz (.md)",
            data=memory_markdown_for_app(app),
            file_name=f"Merksatz-{app.get('id', 'app')}.md",
            mime="text/markdown",
            key=f"dl-memory-{app.get('id')}",
        )

    render_troubleshooting(app)


def render_memory_page(apps: list[dict]) -> None:
    st.markdown(
        "Wenn du in ein paar Wochen nicht mehr weißt, **wo** du entwickelst und **wie** du live gehst: "
        "hier alle Apps. Zum Drucken: Download oder Drucken → PDF."
    )
    st.download_button(
        "Alle Merksätze.md herunterladen",
        data=all_apps_memory_markdown(apps),
        file_name="Merksaetze-alle-Apps.md",
        mime="text/markdown",
    )
    for app in apps:
        name = app.get("name", "?")
        wf = app.get("workflow") or {}
        one = (wf.get("summary") or "")[:80]
        with st.expander(f"{name} — {one}", expanded=False):
            st.markdown(memory_markdown_for_app(app))


def git_for_path(local: str, *, force: bool = False) -> dict:
    """Einzelner Pfad — z. B. auf der App-Detailseite (max. ein Repo)."""
    if not local:
        return empty_git_dict()
    snap = _git_snapshot()
    if force or local not in snap:
        ok, _ = path_diagnosis(local)
        if ok and path_exists(local):
            snap[local] = git_status_to_dict(git_status(local))
        else:
            snap[local] = empty_git_dict("Ordner fehlt")
    return snap[local]


def git_from_snapshot(local: str) -> dict:
    if not full_git_snapshot_ready():
        return empty_git_dict("noch nicht geladen")
    return _git_snapshot().get(local, empty_git_dict("—"))


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
    g = git_for_path(local)
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


def render_open_issues(apps: list[dict], snapshot: dict[str, dict]) -> None:
    missing = []
    dirty_names = []
    for app in apps:
        local = app.get("local_path") or ""
        ok, _ = path_diagnosis(local)
        if not ok:
            missing.append(app.get("name", "?"))
        elif path_exists(local):
            g = snapshot.get(local, {})
            if g.get("dirty"):
                dirty_names.append(app.get("name", "?"))
    if not missing and not dirty_names:
        st.success("**Alles in Ordnung** — alle Pfade vorhanden, keine uncommitteten Änderungen.")
        return
    if missing:
        st.error("**Ordner fehlt:** " + ", ".join(missing))
    if dirty_names:
        st.warning("**Git geändert (uncommitted):** " + ", ".join(dirty_names))


def _batch_checkbox_key(app_id: str) -> str:
    return f"batch_chk_{app_id}"


@st.fragment
def render_batch_git(apps: list[dict], snapshot: dict[str, dict]) -> None:
    dirty = find_dirty_projects(apps, snapshot)
    if not dirty:
        return

    st.subheader("Git: Projekte committen / pushen")
    st.caption(
        "Hake unten **explizit** an, welche Projekte mit uncommitteten Änderungen "
        "in die Aktion sollen."
    )

    for proj in dirty:
        key = _batch_checkbox_key(proj.app_id)
        if key not in st.session_state:
            st.session_state[key] = True

    btn_all, btn_none = st.columns(2)
    with btn_all:
        if st.button("Alle auswählen", key="batch_git_all", use_container_width=True):
            for proj in dirty:
                st.session_state[_batch_checkbox_key(proj.app_id)] = True
    with btn_none:
        if st.button("Alle abwählen", key="batch_git_none", use_container_width=True):
            for proj in dirty:
                st.session_state[_batch_checkbox_key(proj.app_id)] = False

    st.markdown("**Projekte mit Änderungen**")
    selected: list = []
    not_selected: list = []
    for proj in dirty:
        branch = proj.branch or "?"
        extra = f" · {proj.ahead} Commit(s) voraus" if proj.ahead else ""
        label = f"**{proj.name}** — Branch `{branch}`{extra}"
        checked = st.checkbox(
            label,
            key=_batch_checkbox_key(proj.app_id),
        )
        if checked:
            selected.append(proj)
        else:
            not_selected.append(proj)

    st.markdown("**Auswahl**")
    if selected:
        names = ", ".join(p.name for p in selected)
        st.success(f"**Wird ausgeführt ({len(selected)}):** {names}")
    else:
        st.error("**Kein Projekt ausgewählt** — bitte mindestens eines ankreuzen.")

    if not_selected:
        st.caption(
            "**Nicht dabei:** " + ", ".join(p.name for p in not_selected)
        )

    if not selected:
        return

    commit_msg = st.text_input(
        "Commit-Nachricht (gleich für alle ausgewählten Projekte)",
        key="batch_commit_msg",
        placeholder="z. B. Stand nach Cockpit-Update",
    )
    c1, c2 = st.columns(2)
    with c1:
        do_commit = st.checkbox("Commit (git add -A + commit)", value=True, key="batch_do_commit")
    with c2:
        do_push = st.checkbox("Push (git push)", value=False, key="batch_do_push")

    if do_push and not do_commit:
        st.caption("Push ohne Commit: nur wenn der Stand bereits committed ist.")

    st.markdown("**Vorschau**")
    if do_commit and not commit_msg.strip():
        st.caption("Commit-Nachricht fehlt noch.")
    else:
        for line in preview_lines(selected, message=commit_msg, do_commit=do_commit, do_push=do_push):
            st.code(line, language=None)

    if st.button("Aktion ausführen …", type="primary", key="batch_git_prepare"):
        if do_commit and not commit_msg.strip():
            st.error("Bitte eine Commit-Nachricht eingeben.")
        elif not do_commit and not do_push:
            st.error("Bitte Commit und/oder Push aktivieren.")
        else:
            st.session_state["batch_git_pending"] = {
                "ids": [p.app_id for p in selected],
                "message": commit_msg.strip(),
                "do_commit": do_commit,
                "do_push": do_push,
            }

    pending = st.session_state.get("batch_git_pending")
    if pending:
        confirm_names = [
            p.name for p in dirty if p.app_id in set(pending["ids"])
        ]
        st.warning(
            f"**Bestätigung für:** {', '.join(confirm_names)}\n\n"
            f"Commit: **{'ja' if pending['do_commit'] else 'nein'}** · "
            f"Push: **{'ja' if pending['do_push'] else 'nein'}**\n\n"
            "Das kann nicht rückgängig gemacht werden."
        )
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("Ja, jetzt ausführen", key="batch_git_confirm"):
                id_set = set(pending["ids"])
                to_run = [p for p in dirty if p.app_id in id_set]
                results = run_batch(
                    to_run,
                    message=pending["message"],
                    do_commit=pending["do_commit"],
                    do_push=pending["do_push"],
                )
                del st.session_state["batch_git_pending"]
                refresh_paths(_git_snapshot(), [p.local_path for p in to_run])
                st.session_state["git_snapshot_at"] = datetime.now().strftime("%H:%M:%S")
                st.session_state["batch_git_results"] = results
        with col_no:
            if st.button("Abbrechen", key="batch_git_cancel"):
                del st.session_state["batch_git_pending"]

    results = st.session_state.get("batch_git_results")
    if results:
        st.subheader("Ergebnis")
        for r in results:
            icon = "OK" if r.success else "Fehler"
            st.markdown(f"**{r.name}** — {icon}")
            for step in r.steps:
                mark = "OK" if step.ok else "Fehler"
                st.caption(f"{step.action}: {mark} — {step.detail[:500]}")
        if st.button("Ergebnis schließen", key="batch_git_clear_results"):
            del st.session_state["batch_git_results"]


@st.fragment
def render_overview_git_block(apps: list[dict]) -> None:
    """Git-Scan und Batch-Aktionen — Änderungen hier blockieren nicht die ganze Seite."""
    if not full_git_snapshot_ready():
        if not st.session_state.get("overview_git_auto_attempted"):
            st.session_state["overview_git_auto_attempted"] = True
            with st.spinner("Git-Status wird beim ersten Besuch ermittelt …"):
                load_full_git_snapshot(apps)
        else:
            st.info("**Git-Status** ist noch nicht geladen.")
            if st.button(
                "Git-Status für alle Projekte laden",
                type="primary",
                key="overview_load_git",
            ):
                with st.spinner("Git-Status wird ermittelt …"):
                    load_full_git_snapshot(apps)
            return

    ts = st.session_state.get("git_snapshot_at", "—")
    c1, c2 = st.columns([3, 1])
    with c1:
        st.caption(f"Git-Stand: **{ts}** — nur bei Bedarf neu laden.")
    with c2:
        if st.button("Git aktualisieren", key="overview_refresh_git", use_container_width=True):
            with st.spinner("Git-Status wird aktualisiert …"):
                load_full_git_snapshot(apps)

    snapshot = _git_snapshot()
    render_open_issues(apps, snapshot)
    render_batch_git(apps, snapshot)


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
    wf = app.get("workflow") or {}
    st.markdown(f"**{name}**")
    if wf.get("summary"):
        st.caption(wf["summary"][:90] + ("…" if len(wf.get("summary", "")) > 90 else ""))
    elif cat:
        st.caption(cat["short"])
    pa = primary_action_hint(app)
    if pa:
        st.caption(f"Start: {pa[0]}")
    if ok:
        st.caption(f"✅ Ordner · Git: {git_label(git_from_snapshot(local))}")
    else:
        st.caption("❌ Ordner fehlt")


def render_overview(apps: list[dict]) -> None:
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


def render_app_detail(app: dict) -> None:
    name = app.get("name", app.get("id", "?"))
    local = app.get("local_path") or ""
    ok, path_msg = path_diagnosis(local)

    st.header(name)
    render_app_memory_hub(app)

    if not ok and path_msg:
        st.error(path_msg)

    if app.get("live_url"):
        st.link_button("Live-App öffnen (Vercel)", app["live_url"])

    if ok and local:
        if st.button("Git für diese App aktualisieren", key=f"git-refresh-{app.get('id')}"):
            git_for_path(local, force=True)
            st.session_state["git_snapshot_at"] = datetime.now().strftime("%H:%M:%S")
        st.caption(f"Git: {git_label(git_for_path(local))}")

    render_git_alerts(app, local if ok else "")
    render_tool_diagnostics(app, path_ok=ok)

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
        with st.expander("Schritt für Schritt (aus apps.yaml)", expanded=True):
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
        with st.expander("Voraussetzungen (manuell / Doku)"):
            st.caption(
                "Statische Liste aus apps.yaml — ersetzt keine Live-Prüfung oben. "
                "Typische Fehler (PATH, fehlendes npm install) zeigt **Umgebung & Werkzeuge**."
            )
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
        clear_git_snapshot()
        clear_tool_check_cache()
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
    elif page_id == "__memory__":
        st.title("Merksätze")
        render_memory_page(display_apps if display_apps else apps)
    elif page_id == "__quickref__":
        st.title("Schnellreferenz")
        render_quickref_page(display_apps if display_apps else apps)
    elif page_id == "__overview__":
        st.title("Übersicht")
        overview_apps = display_apps if display_apps else apps
        render_overview_git_block(overview_apps)
        st.divider()
        render_overview(overview_apps)
        with st.expander("Playbook.md"):
            md = playbook_markdown(display_apps if display_apps else apps)
            st.download_button("PLAYBOOK.md", data=md, file_name="PLAYBOOK.md", mime="text/markdown")
    elif page_id:
        app = next(a for a in display_apps if a.get("id") == page_id)
        render_app_detail(app)

    st.sidebar.divider()
    st.sidebar.caption("Vergessen? → Merksätze · Drucken: Schnellreferenz oder Merksätze.md")


if __name__ == "__main__":
    main()
