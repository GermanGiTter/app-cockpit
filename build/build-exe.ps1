# App-Cockpit als Windows-.exe bauen (PyInstaller, onedir)
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

function Find-Python {
    $candidates = @(
        "$env:LOCALAPPDATA\Python\bin\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) {
            $bits = & $p -c "import struct; print(struct.calcsize('P')*8)" 2>$null
            if ($bits -eq "64") { return $p }
        }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $v = & py -3 -c "import sys; print(sys.executable)" 2>$null
        if ($v -and (Test-Path $v.Trim())) { return $v.Trim() }
    }
    foreach ($cmd in @("python", "python3")) {
        if (Get-Command $cmd -ErrorAction SilentlyContinue) {
            $v = & $cmd -c "import sys; print(sys.executable)" 2>$null
            if ($v -and (Test-Path $v.Trim())) { return $v.Trim() }
        }
    }
    throw "Kein Python gefunden. Bitte Python 3.10+ (64-bit) installieren."
}

$python = Find-Python
Write-Host "Python: $python"

$venv = Join-Path $Root ".venv-build"
$venvPy = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Erstelle Build-Umgebung .venv-build ..."
    & $python -m venv $venv
}
& $venvPy -m pip install --upgrade pip -q
& $venvPy -m pip install -r (Join-Path $Root "cockpit\requirements.txt") -q
& $venvPy -m pip install -r (Join-Path $Root "build\requirements-build.txt") -q

Write-Host "PyInstaller startet (kann einige Minuten dauern) ..."
& $venvPy -m PyInstaller (Join-Path $Root "build\app-cockpit.spec") --noconfirm --distpath (Join-Path $Root "dist") --workpath (Join-Path $Root "build\pyi-work")

$outDir = Join-Path $Root "dist\App-Cockpit"
$exe = Join-Path $outDir "App-Cockpit.exe"
if (-not (Test-Path $exe)) {
    throw "Build fehlgeschlagen: $exe nicht gefunden"
}

# apps.yaml neben die exe (editierbar; überschreibt nicht wenn schon vorhanden)
$yamlDest = Join-Path $outDir "apps.yaml"
if (-not (Test-Path $yamlDest)) {
    Copy-Item (Join-Path $Root "apps.yaml") $yamlDest
}

$readme = @"
App-Cockpit (Windows)
=====================

Start: Doppelklick auf App-Cockpit.exe
Browser: http://127.0.0.1:8501

apps.yaml in diesem Ordner bearbeiten = App-Liste ändern.
Zum Beenden: dieses Fenster schließen (Task-Manager falls nötig).

Neu bauen: im Projektordner build\build-exe.ps1 ausführen.
"@
Set-Content -Path (Join-Path $outDir "LESEN.txt") -Value $readme -Encoding UTF8

Write-Host ""
Write-Host "Fertig: $exe"
Write-Host "Ordner zum Kopieren/Verknüpfen: $outDir"
