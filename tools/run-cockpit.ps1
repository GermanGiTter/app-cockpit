# App-Cockpit starten (Streamlit)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Erstelle virtuelle Umgebung ..."
    py -3 -m venv .venv
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r (Join-Path $Root "cockpit\requirements.txt")
}

Write-Host "Starte App-Cockpit -> http://localhost:8501"
& $venvPython -m streamlit run (Join-Path $Root "cockpit\app.py")
