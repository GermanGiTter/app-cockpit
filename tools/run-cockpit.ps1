# App-Cockpit starten (Streamlit)
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
    throw "Kein Python 64-bit gefunden. Installiere Python von python.org oder nutze die EXE in dist\App-Cockpit\."
}

$systemPython = Find-Python
Write-Host "Python: $systemPython"

$venvDir = Join-Path $Root ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    if (Test-Path $venvDir) {
        Write-Host "Entferne unvollständige .venv ..."
        Remove-Item -Recurse -Force $venvDir
    }
    Write-Host "Erstelle virtuelle Umgebung ..."
    & $systemPython -m venv $venvDir
    if (-not (Test-Path $venvPython)) {
        throw "venv fehlgeschlagen: $venvPython nicht erstellt"
    }
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r (Join-Path $Root "cockpit\requirements.txt")
}

Write-Host "Starte App-Cockpit -> http://localhost:8501"
& $venvPython -m streamlit run (Join-Path $Root "cockpit\app.py")
