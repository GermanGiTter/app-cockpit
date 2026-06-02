"""Release-Checklisten (Session-State, pro App)."""

from __future__ import annotations

DEFAULT_ITEMS: dict[str, list[tuple[str, str]]] = {
  "mac_ios": [
    ("win_dev", "Am PC entwickelt und getestet"),
    ("git_push", "Änderungen committed und zu GitHub gepusht"),
    ("mac_pull", "Auf dem Mac: git pull ausgeführt"),
    ("mac_build", "Auf dem Mac: Build auf Gerät (Xcode/Flutter/Expo)"),
  ],
  "vercel": [
    ("local_test", "Lokal mit dev getestet"),
    ("git_push", "committed und gepusht (Vercel-Deploy)"),
    ("vercel_check", "Vercel-Deploy und PUSH-CHECKLISTE geprüft"),
  ],
  "android_usb": [
    ("studio_sync", "Android Studio: Gradle Sync OK"),
    ("device_run", "App auf Gerät installiert/gestartet"),
  ],
  "windows": [
    ("run_ok", "App am PC gestartet — funktioniert"),
  ],
  "local": [
    ("run_ok", "Lokal gestartet — funktioniert"),
  ],
}


def items_for_app(app: dict) -> list[tuple[str, str]]:
  custom = app.get("checklist")
  if custom:
    return [(c["id"], c["label"]) for c in custom]
  release = (app.get("workflow") or {}).get("release_on", "local")
  return DEFAULT_ITEMS.get(release, DEFAULT_ITEMS["local"])


def session_key(app_id: str, item_id: str) -> str:
  return f"chk_{app_id}_{item_id}"
