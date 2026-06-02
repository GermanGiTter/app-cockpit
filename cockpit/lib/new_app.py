"""YAML-Vorlage für neue Apps (Formular)."""

from __future__ import annotations

import textwrap


def build_app_yaml(
  *,
  app_id: str,
  name: str,
  description: str,
  local_path: str,
  release_on: str,
  github: str = "",
  repo_folder: str = "",
) -> str:
  gh_line = f"\n  github: {github}" if github.strip() else ""
  folder_line = f"\n  repo_folder: {repo_folder}" if repo_folder.strip() else ""
  summary = {
    "mac_ios": "Windows entwickeln, Mac baut, iPhone/iPad.",
    "vercel": "Windows testen, Live über Vercel (git push).",
    "android_usb": "Android Studio am PC, USB aufs Handy.",
    "windows": "Nur Windows-PC.",
    "local": "Nur lokal auf dem PC.",
  }.get(release_on, "Anpassen.")

  return textwrap.dedent(
    f"""
    - id: {app_id}
      name: {name}
      status: active
      description: {description}
      stack: []
      tags: []
      local_path: {local_path}{gh_line}{folder_line}
      workflow:
        dev_on: windows
        release_on: {release_on}
        summary: "{summary}"
      commands_setup: |
        # Erstes Mal — anpassen
        cd {repo_folder or app_id}
      commands_windows:
        dev: |
          cd {repo_folder or app_id}
          # Startbefehl eintragen
    """
  ).strip() + "\n"
