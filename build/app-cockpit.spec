# PyInstaller: App-Cockpit.exe (Windows, onedir)
# Build: build\build-exe.ps1

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None
root = Path(SPECPATH).parent

st_datas, st_binaries, st_hidden = collect_all("streamlit")
al_datas, al_binaries, al_hidden = collect_all("altair")
pd_datas, pd_binaries, pd_hidden = collect_all("pandas")

# Nur app.yaml + app.py als Dateien; cockpit/lib wird als Python-Module gebündelt
cockpit_hidden = [
    "cockpit",
    "cockpit.lib",
    "cockpit.lib.git_batch",
    "cockpit.lib.git_snapshot",
    "cockpit.lib.tool_checks",
    "cockpit.lib.app_memory",
    "cockpit.lib.playground_scan",
    "cockpit.lib.updates",
    "cockpit.lib.checklist",
    "cockpit.lib.commands",
    "cockpit.lib.manifest",
    "cockpit.lib.new_app",
    "cockpit.lib.paths",
    "cockpit.lib.quickref",
    "cockpit.lib.status",
    "cockpit.lib.workflow_guide",
]

datas = (
    [
        (str(root / "apps.yaml"), "."),
        (str(root / "cockpit" / "app.py"), "cockpit"),
        (str(root / ".streamlit" / "config.toml"), ".streamlit"),
    ]
    + st_datas
    + al_datas
    + pd_datas
)
binaries = st_binaries + al_binaries + pd_binaries
hiddenimports = (
    [
        "streamlit.web.cli",
        "yaml",
        "tornado.platform.asyncio",
        "click",
    ]
    + cockpit_hidden
    + st_hidden
    + al_hidden
    + pd_hidden
)

a = Analysis(
    [str(root / "cockpit" / "launcher.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="App-Cockpit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="App-Cockpit",
)
