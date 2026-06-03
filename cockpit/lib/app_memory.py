"""Merksätze, Ablauf-Klartext und typische Probleme — für „in ein paar Wochen vergessen“."""

from __future__ import annotations

from cockpit.lib.commands import get_command_blocks
from cockpit.lib.status import pick_primary_command
from cockpit.lib.workflow_guide import CATEGORIES, category_for_app, route_lines

COMMAND_LEGEND: dict[str, tuple[str, str]] = {
    "install": ("Einmal einrichten", "Nach Klon oder neuem PC — Dependencies holen"),
    "update": ("Stand aktualisieren", "git pull und Abhängigkeiten nachziehen"),
    "dev": ("Täglich testen", "Haupt-Befehl zum Entwickeln am Windows-PC"),
    "dev_gui": ("GUI starten", "Desktop-Oberfläche / Tauri dev"),
    "dev_ipad": ("Im WLAN testen", "z. B. iPad im gleichen Netz"),
    "dev_alt_port": ("Anderer Port", "Wenn 8501 schon belegt ist"),
    "build": ("Produktions-Build", "Web-Build vor Deploy oder Capacitor"),
    "build_exe": ("EXE bauen", "Windows-Programm neu packen (App-Cockpit)"),
    "release": ("Release-Modus", "Näher an Produktion testen"),
    "test": ("Tests", "Automatische Tests im Projekt"),
    "android": ("Android", "Expo/Android am PC"),
    "ios": ("iOS (Mac)", "Nur auf dem Mac ausführen"),
    "ios_setup": ("iOS vorbereiten", "Pods / Xcode-Setup"),
    "web": ("Im Browser", "Web-Variante starten"),
    "apk": ("APK bauen", "Android-Paket erzeugen"),
    "sync": ("Mac: Repo holen", "git pull + deps auf dem Mac"),
    "ios_pods": ("Mac: CocoaPods", "Nach ios-Änderungen"),
    "run_device": ("Mac: Gerät", "Auf iPhone/iPad starten"),
    "cap:ios": ("Mac: Xcode", "Capacitor öffnet Xcode"),
}

RELEASE_IF_LOST: dict[str, str] = {
    "mac_ios": (
        "**Start hier:** Am Windows-PC im Projektordner den Befehl **dev** (Schnellstart). "
        "Wenn es ums iPhone/iPad geht: zuerst am PC **git push**, dann am Mac **git pull** "
        "und die Mac-Befehle unten (Flutter/npm + Xcode)."
    ),
    "vercel": (
        "**Start hier:** Am PC **npm run dev** testen. Für die Live-Seite: **git commit + push** — "
        "Vercel baut von allein. URL unten „Live-App öffnen“. Checkliste PUSH-CHECKLISTE.md nicht vergessen."
    ),
    "android_usb": (
        "**Start hier:** Android Studio → Projektordner öffnen → Gradle Sync → USB-Debugging am Handy → Run (▶). "
        "Kein npm, kein Mac — alles über Android Studio."
    ),
    "windows": (
        "**Start hier:** Projektordner öffnen, Befehl **dev** oder **dev_gui** (Schnellstart). "
        "Alles bleibt auf diesem Windows-PC."
    ),
    "local": (
        "**Start hier:** Befehl **dev** (Streamlit) oder Doppelklick auf die **EXE** (App-Cockpit). "
        "Nur dieser Rechner — nichts deployen."
    ),
}

RELEASE_BULLETS: dict[str, list[str]] = {
    "mac_ios": [
        "Entwickeln und testen: **Windows-PC** im Playground-Ordner.",
        "Aufs Gerät: Build läuft auf dem **Mac** (Flutter / Expo / Capacitor + Xcode).",
        "Übertragung: **GitHub** (push am PC, pull am Mac) — Ordner nicht per USB kopieren.",
        "Vor dem Mac: uncommittete Änderungen? → **commit + push**.",
    ],
    "vercel": [
        "Lokal testen: **npm run dev** im Projektordner retrograde-filament.",
        "Live: nur **git push** → Vercel. Env-Variablen im **Vercel-Dashboard**.",
        "Kein Mac, kein App Store — Nutzung im **Browser** (PWA).",
    ],
    "android_usb": [
        "Nur **Android Studio** am Windows-PC.",
        "Handy per **USB**, USB-Debugging aktiv.",
        "Doku im Projekt: **INSTALLATION.md** (Alles Zu).",
    ],
    "windows": [
        "Ein Rechner: **Windows-PC** — entwickeln und starten am selben Ort.",
        "Typisch: **dev** / **dev_gui** oder Programm aus dem Build-Ordner.",
    ],
    "local": [
        "Läuft nur bei dir: **Browser** (Streamlit) oder **EXE**.",
        "Kein Vercel, kein Handy-Release nötig.",
        "Python-Apps: oft **.venv** aktivieren vor dev.",
    ],
}

STACK_TROUBLESHOOTING: dict[str, list[tuple[str, str]]] = {
    "node": [
        (
            "„npm ist nicht erkannt“",
            "Node.js LTS installieren, **neues** PowerShell-Fenster, `node -v` und `npm -v` testen.",
        ),
        (
            "npm install schlägt fehl",
            "Im Projektordner: Ordner `node_modules` löschen, `package-lock.json` optional löschen, "
            "dann `npm install` erneut. Antivirus/OneDrive am Ordner prüfen.",
        ),
        (
            "Port schon belegt (dev)",
            "Anderen Port nutzen (z. B. dev_alt_port) oder alten Prozess beenden.",
        ),
        (
            "Änderungen live, aber lokal alt",
            "Vercel-Apps: **git push** vergessen? Lokal mit `git pull` und erneut `npm run dev` testen.",
        ),
    ],
    "flutter": [
        (
            "„flutter ist nicht erkannt“",
            "Flutter SDK installieren, PATH setzen, Terminal neu starten, `flutter --version`.",
        ),
        (
            "flutter pub get / build Fehler",
            "Im Projektroot: `flutter clean`, dann `flutter pub get`. Bei iOS: `cd ios`, `pod install`.",
        ),
        (
            "iPhone zeigt alte Version",
            "Debug oft nur per **`flutter run`**, nicht Home-Icon. Release: `flutter run --release` am Mac.",
        ),
        (
            "Gerät wird nicht gefunden",
            "USB verbinden, `flutter devices`. Am Mac: Xcode-Lizenz / Vertrauen auf dem Gerät.",
        ),
    ],
    "expo": [
        (
            "Expo startet nicht",
            "Im Projekt: `npm install`, dann `npm start`. Firewall/WLAN für Handy-Test prüfen.",
        ),
        (
            "iOS-Build",
            "Läuft auf dem **Mac**: `npm run ios` nach git pull und npm install.",
        ),
    ],
    "python": [
        (
            "py / python nicht gefunden",
            "Python 64-bit von python.org oder `%LOCALAPPDATA%\\Python\\bin\\python.exe`. "
            "Cockpit: `tools\\run-cockpit.ps1`.",
        ),
        (
            "Modul fehlt (ImportError)",
            "Venv aktivieren: `.\\.venv\\Scripts\\Activate.ps1`, dann `pip install -r requirements.txt`.",
        ),
        (
            "Streamlit Port belegt",
            "`dev_alt_port` nutzen oder anderen Streamlit-Prozess beenden.",
        ),
    ],
    "rust": [
        (
            "Tauri / cargo Fehler",
            "`rustup update`, im Projekt `npm install` und `npm run tauri dev`. "
            "WebView2 auf Windows muss installiert sein.",
        ),
    ],
    "android": [
        (
            "Gradle Sync failed",
            "Android Studio: File → Invalidate Caches, JDK/Gradle in Settings prüfen, Internet für Downloads.",
        ),
        (
            "Gerät nicht sichtbar",
            "USB-Debugging, Kabel, Treiber. `adb devices` in PowerShell (wenn adb im PATH).",
        ),
    ],
}

RELEASE_TROUBLESHOOTING: dict[str, list[tuple[str, str]]] = {
    "mac_ios": [
        (
            "Am Mac „alte“ Dateien",
            "Am PC gepusht? Am Mac im Projektordner: `git pull`, dann flutter pub get / npm install.",
        ),
        (
            "Xcode / Signing",
            "Apple-ID in Xcode, Team wählen, Gerät vertrauen. Capacitor: `npm run cap:ios` dann Run in Xcode.",
        ),
    ],
    "vercel": [
        (
            "Deploy ok, Seite kaputt",
            "**PUSH-CHECKLISTE.md** im Repo — DB, Env-Vars, Tenant. Vercel-Logs im Dashboard.",
        ),
        (
            "Lokal ok, Live nicht",
            "Env-Variablen nur lokal reichen nicht — im **Vercel-Dashboard** setzen und Redeploy.",
        ),
    ],
    "android_usb": [
        (
            "Run grau / Install failed",
            "MinSdk, USB-Debugging, ggf. APK manuell (Befehl apk / INSTALLATION.md).",
        ),
    ],
}


def when_lost(app: dict) -> str:
    release = (app.get("workflow") or {}).get("release_on", "local")
    return RELEASE_IF_LOST.get(release, RELEASE_IF_LOST["local"])


def memory_bullets(app: dict) -> list[str]:
    release = (app.get("workflow") or {}).get("release_on", "local")
    bullets = list(RELEASE_BULLETS.get(release, RELEASE_BULLETS["local"]))
    notes = app.get("notes") or []
    if notes:
        bullets.append(f"**Projekt-Hinweis:** {notes[0]}")
    return bullets


def troubleshooting_for_app(app: dict) -> list[tuple[str, str]]:
    tags = {s.lower() for s in (app.get("stack") or [])}
    release = (app.get("workflow") or {}).get("release_on", "")
    seen: set[str] = set()
    out: list[tuple[str, str]] = []

    def add(items: list[tuple[str, str]]) -> None:
        for title, fix in items:
            if title in seen:
                continue
            seen.add(title)
            out.append((title, fix))

    if release:
        add(RELEASE_TROUBLESHOOTING.get(release, []))
    for tag in ("node", "flutter", "expo", "python", "rust", "android"):
        if tag in tags:
            add(STACK_TROUBLESHOOTING.get(tag, []))
    return out


def command_legend_for_app(app: dict) -> list[tuple[str, str, str]]:
    """(Schlüssel, Kurzname, Wann nutzen) — nur vorhandene Befehle."""
    setup, windows, mac = get_command_blocks(app)
    blocks: list[tuple[str, dict[str, str]]] = [
        ("Einrichtung", setup or {}),
        ("Windows", windows or {}),
        ("Mac", mac or {}),
    ]
    legacy = app.get("commands") or {}
    if legacy and not windows:
        blocks.append(("Befehle", legacy))

    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for _block, cmds in blocks:
        for key in cmds:
            if key in seen:
                continue
            seen.add(key)
            label, when = COMMAND_LEGEND.get(key, (key, "Siehe Skript unten"))
            out.append((key, label, when))
    return out


def primary_action_hint(app: dict) -> tuple[str, str] | None:
    setup, windows, _mac = get_command_blocks(app)
    for block in (windows, app.get("commands") or {}, setup):
        if not block:
            continue
        primary = pick_primary_command(block)
        if primary:
            key, _ = primary
            label, when = COMMAND_LEGEND.get(key, (key, ""))
            return label, when
    return None


def memory_markdown_for_app(app: dict) -> str:
    """Eine App — zum Kopieren / Merksätze-Seite."""
    name = app.get("name", "?")
    wf = app.get("workflow") or {}
    cat = category_for_app(app)
    lines = [f"## {name}\n", f"**Kurz:** {wf.get('summary', app.get('description', ''))}\n\n"]
    lines.append(f"{when_lost(app)}\n\n")
    if cat:
        lines.append(f"**Muster:** {cat['title']} — {cat['short']}\n\n")
        lines.append(f"- Nicht nötig / falsch: {cat['never']}\n\n")
    lines.append("### Ablauf\n")
    for label, text in route_lines(app):
        lines.append(f"- **{label}:** {text}\n")
    lines.append("\n### Merken\n")
    for b in memory_bullets(app):
        lines.append(f"- {b}\n")
    pa = primary_action_hint(app)
    if pa:
        lines.append(f"\n**Schnellstart:** {pa[0]} — {pa[1]}\n")
    local = app.get("local_path") or ""
    if local:
        lines.append(f"\n**Ordner:** `{local}`\n")
    if app.get("live_url"):
        lines.append(f"**Live:** {app['live_url']}\n")
    legend = command_legend_for_app(app)
    if legend:
        lines.append("\n### Befehle (Bedeutung)\n")
        for key, label, when in legend:
            lines.append(f"- `{key}` — **{label}:** {when}\n")
    tips = troubleshooting_for_app(app)
    if tips:
        lines.append("\n### Typische Probleme\n")
        for title, fix in tips:
            lines.append(f"- **{title}:** {fix}\n")
    return "".join(lines)


def all_apps_memory_markdown(apps: list[dict]) -> str:
    from cockpit.lib.manifest import sort_apps

    parts = [
        "# App-Cockpit — Merksätze (alle Apps)\n\n",
        "_Wenn du in ein paar Wochen nicht mehr weißt, wie es ging — diese Seite ausdrucken oder als PDF speichern._\n\n",
    ]
    for app in sort_apps(apps):
        parts.append(memory_markdown_for_app(app))
        parts.append("\n---\n\n")
    return "".join(parts)
