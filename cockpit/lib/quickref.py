"""Schnellreferenz — eine Seite, druckbar."""

from __future__ import annotations

from cockpit.lib.app_memory import primary_action_hint, when_lost
from cockpit.lib.workflow_guide import CATEGORIES, apps_in_category


def quickref_markdown(apps: list[dict]) -> str:
  lines = [
    "# App-Cockpit — Schnellreferenz\n",
    "| App | Muster | Kurzablauf | Wenn vergessen → |\n",
    "|-----|--------|------------|------------------|\n",
  ]
  for app in apps:
    name = app.get("name", "?")
    wf = app.get("workflow") or {}
    cat = next((c for c in CATEGORIES if c["release_on"] == wf.get("release_on")), None)
    pattern = cat["title"] if cat else "—"
    summary = wf.get("summary", app.get("description", "")).replace("|", "/")
    lost = when_lost(app).replace("|", "/").replace("\n", " ")[:120]
    if len(lost) >= 120:
      lost += "…"
    lines.append(f"| {name} | {pattern} | {summary} | {lost} |\n")

  lines.append("\n## Pro App: Schnellstart\n")
  for app in apps:
    pa = primary_action_hint(app)
    name = app.get("name", "?")
    if pa:
      lines.append(f"- **{name}:** {pa[0]} — {pa[1]}\n")
    else:
      lines.append(f"- **{name}:** Siehe Cockpit-Detailseite\n")

  lines.append("\n## Muster im Detail\n")
  for cat in CATEGORIES:
    group = apps_in_category(apps, cat["release_on"])
    if not group:
      continue
    names = ", ".join(a.get("name", "?") for a in group)
    lines.append(f"\n### {cat['title']}\n")
    lines.append(f"**Apps:** {names}\n\n")
    lines.append(f"- **Entwickeln:** {cat['where_dev']}\n")
    lines.append(f"- **Übertragen:** {cat['how_transfer']}\n")
    lines.append(f"- **Nutzen:** {cat['where_run']}\n")

  lines.append(
    "\n---\n_Gedruckt oder als PDF aus dem Browser — Stand aus apps.yaml._\n"
  )
  return "".join(lines)
