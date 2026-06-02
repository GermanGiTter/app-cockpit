"""Klartext: Wo entwickeln, wohin übertragen, wo ausführen."""

from __future__ import annotations

# release_on-Wert aus apps.yaml → Kategorie
CATEGORIES: list[dict] = [
    {
        "release_on": "mac_ios",
        "title": "Windows → Mac → iPhone / iPad",
        "short": "PC entwickeln · Mac baut · Gerät startet",
        "where_dev": "Dein Windows-PC (Playground-Ordner)",
        "where_transfer": "Über GitHub — kein USB-Stick mit dem Projektordner",
        "how_transfer": "Am PC: git commit + git push. Am Mac: git clone oder git pull.",
        "where_run": "Auf dem Mac in Xcode / Flutter / Expo — Gerät per USB",
        "never": "Nicht auf Vercel. Nicht nur am PC fürs iPhone-Release.",
    },
    {
        "release_on": "vercel",
        "title": "Windows → Vercel (Internet)",
        "short": "PC testen · Live nur in der Cloud",
        "where_dev": "Windows-PC, Ordner retrograde-filament",
        "where_transfer": "Git push → Vercel baut automatisch",
        "how_transfer": "git commit, git push. Env-Variablen im Vercel-Dashboard.",
        "where_run": "Handy/PC: URL im Browser (PWA) — kein App Store",
        "never": "Kein Mac. Kein Kopieren des Ordners auf einen Server per Hand.",
    },
    {
        "release_on": "android_usb",
        "title": "Windows → Android-Handy (USB)",
        "short": "Android Studio am PC · APK/Run aufs Handy",
        "where_dev": "Windows-PC mit Android Studio",
        "where_transfer": "USB-Kabel — Run oder APK installieren",
        "how_transfer": "Android Studio ▶ Run, oder APK bauen und aufs Gerät kopieren",
        "where_run": "Direkt auf dem Android-Handy",
        "never": "Kein Mac. Kein Vercel.",
    },
    {
        "release_on": "windows",
        "title": "Nur Windows-PC",
        "short": "Alles auf einem Rechner",
        "where_dev": "Windows-PC",
        "where_transfer": "Nicht nötig",
        "how_transfer": "—",
        "where_run": "Gleicher PC (Programm starten)",
        "never": "Kein Mac, kein Handy-Release.",
    },
    {
        "release_on": "local",
        "title": "Nur lokal auf dem PC",
        "short": "Browser oder EXE — nichts online",
        "where_dev": "Windows-PC",
        "where_transfer": "Nicht nötig",
        "how_transfer": "—",
        "where_run": "Browser (Streamlit) oder Doppelklick EXE",
        "never": "Kein git push für Live-Betrieb nötig.",
    },
]

_CATEGORY_BY_RELEASE = {c["release_on"]: c for c in CATEGORIES}


def category_for_app(app: dict) -> dict | None:
    release = (app.get("workflow") or {}).get("release_on")
    if release:
        return _CATEGORY_BY_RELEASE.get(release)
    return None


def apps_in_category(apps: list[dict], release_on: str) -> list[dict]:
    return [
        a
        for a in apps
        if (a.get("workflow") or {}).get("release_on") == release_on
    ]


def route_lines(app: dict) -> list[tuple[str, str]]:
    """Drei Zeilen für die Detail-Karte: Label → Klartext."""
    cat = category_for_app(app)
    name = app.get("name", "?")
    if not cat:
        return [
            ("Entwickeln", "Siehe Schritte unten"),
            ("Übertragen", "—"),
            ("Starten / Nutzen", "—"),
        ]
    release = cat["release_on"]
    if release == "mac_ios":
        return [
            ("1 · Entwickeln", f"Am **Windows-PC** im Projektordner ({name})"),
            ("2 · Übertragen", "**Git push** (PC) → **git pull** (Mac) — Ordner nicht per USB kopieren"),
            ("3 · Auf Gerät", "**Am Mac** bauen und auf iPhone/iPad installieren/starten"),
        ]
    if release == "vercel":
        return [
            ("1 · Testen", f"Am **Windows-PC**: npm run dev"),
            ("2 · Live stellen", "**git push** → Vercel deployt"),
            ("3 · Nutzen", "**Browser** auf Handy/PC mit der Vercel-URL"),
        ]
    if release == "android_usb":
        return [
            ("1 · Entwickeln", "**Windows-PC** + Android Studio"),
            ("2 · Aufs Handy", "**USB** — Run oder APK"),
            ("3 · Nutzen", "App-Icon auf dem Android-Handy"),
        ]
    if release == "windows":
        return [
            ("1 · Entwickeln", "**Windows-PC** im Projektordner"),
            ("2 · Übertragen", "Nicht nötig"),
            ("3 · Starten", "Programm/Skript auf dem **gleichen PC**"),
        ]
    # local
    return [
        ("1 · Entwickeln", "**Windows-PC**"),
        ("2 · Übertragen", "Nicht nötig"),
        ("3 · Starten", "Lokal im **Browser** oder per **EXE**"),
    ]
