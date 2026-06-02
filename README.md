# App-Cockpit

Zentrales **Nachschlagebuch** für deine Projekte: eine Datei (`apps.yaml`), optional eine kleine **Streamlit-Oberfläche**.

## Pfad

`C:\Users\rare\.gemini\antigravity\playground\app-cockpit`

## Dateien

| Datei | Zweck |
|-------|--------|
| `apps.yaml` | Register aller Apps (Befehle, Pfade, Stack, Hinweise) |
| `cockpit/app.py` | Web-UI zum Durchsuchen und Kopieren von Befehlen |
| `README.md` | Diese Anleitung |

## Register pflegen

Pro App in `apps.yaml`:

- `id`, `name`, `description`, `status` (`active` / `draft`)
- `stack`, `tags`, `local_path`, optional `github`
- `commands` — z. B. `install`, `update`, `dev`, `test`
- `prerequisites`, `notes`

Neue App: Block am Ende von `apps:` anfügen oder einen `draft`-Eintrag ausfüllen.

## Cockpit als Windows-.exe

**Einmal bauen** (Python 3.10+ 64-bit nötig):

```powershell
C:\Users\rare\.gemini\antigravity\playground\app-cockpit\build\build-exe.ps1
```

Ergebnis:

`dist\App-Cockpit\App-Cockpit.exe` — **Doppelklick** startet das Cockpit und öffnet den Browser.

- `apps.yaml` liegt **im gleichen Ordner** wie die `.exe` (editierbar, ohne Neu-Build).
- Den ganzen Ordner `App-Cockpit` kannst du z. B. nach `Desktop\App-Cockpit` kopieren und dort die Verknüpfung zur `.exe` anlegen.
- Beenden: Streamlit-Prozess beenden (Fenster/Task-Manager) oder Browser-Tab schließen und Prozess beenden.

Hinweis: Der Build erzeugt einen **Ordner** mit der `.exe` und Bibliotheken (typisch für Streamlit, ca. einige hundert MB). Das ist normal.

## Cockpit starten (Entwicklung / ohne Build)

**Ein Klick (empfohlen):**

```powershell
C:\Users\rare\.gemini\antigravity\playground\app-cockpit\tools\run-cockpit.ps1
```

Legt bei Bedarf `.venv` an und öffnet **http://localhost:8501**.

**Manuell:**

```powershell
cd C:\Users\rare\.gemini\antigravity\playground\app-cockpit
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r cockpit\requirements.txt
streamlit run cockpit\app.py
```

## Was die Oberfläche kann

- **Übersicht** — alle 7 Apps: Ordner vorhanden?, Git-Branch, sauber/geändert, ahead/behind
- **App-Detail** — Beschreibung, Schnellstart (`dev` o. Ä.), alle Befehle mit festem `Set-Location`
- **Filter** — Suche, Tags, Stack (Sidebar)
- **PowerShell** — Schnellstart optional in neuem Fenster (mit Bestätigung)
- **PLAYBOOK.md** — Download aus derselben `apps.yaml`

Daten pflegen weiter nur in **`apps.yaml`** — UI liest dieselbe Datei.

## Eingetragene Apps (8)

| App | Ordner |
|-----|--------|
| App-Cockpit | `app-cockpit` |
| Chrona | `chrona` |
| ChordQuest | `chordquest` |
| Cellora | `Cello` |
| TD-9 Studio Manager | `TD-9` |
| Kurs-Import | `kurs-import` |
| Alles Zu | `ALLES-ZU` |
| Einkaufsliste | `retrograde-filament` |

Weitere Projekte: neuen Block in `apps.yaml` anlegen oder Pfade schicken.

## Nächste Stufen (optional)

- Desktop-Verknüpfung auf `run-cockpit.ps1`
- GitHub-URLs für alle Repos in `apps.yaml`
- Ein Klick pro Befehlstyp (nicht nur Schnellstart)
- Eigenes Git-Repo für `app-cockpit` + Push zu GitHub
