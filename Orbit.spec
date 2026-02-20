# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Files/folders to exclude from the build to reduce size
EXCLUDE_FROM_BINARIES = [
    'opengl32sw.dll',      # Software OpenGL (~20MB) - not needed with hardware GPU
    'Qt6Pdf.dll',          # PDF support - not used
    'Qt6Qml.dll',          # QML engine - not used
    'Qt6Quick.dll',        # Quick UI - not used  
    'Qt6QmlModels.dll',    # QML Models - not used
    'Qt6QmlMeta.dll',      # QML Meta - not used
    'Qt6QmlWorkerScript.dll',  # QML Worker - not used
    'd3dcompiler_47.dll',  # DirectX compiler - usually not needed
]

EXCLUDE_FROM_DATAS = [
    'translations/',       # All Qt translations
    'PySide6/translations/', # PySide6 translations
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'tcl', 'tk', 'matplotlib', 'numpy', 'pandas', 
              'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Helper function to check if file should be kept
def should_keep_translation(path):
    """Keep only Turkish translations, remove all others"""
    if 'translations/' in path or 'translations\\\\' in path:
        return '_tr.qm' in path  # Keep only Turkish
    return True

# Remove unwanted binaries and non-Turkish translations
a.binaries = [b for b in a.binaries 
              if not any(exc in b[0] for exc in EXCLUDE_FROM_BINARIES)
              and should_keep_translation(b[0])]

# Remove unwanted data files - keep only Turkish translations
a.datas = [d for d in a.datas if should_keep_translation(d[0])]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Orbit',
    icon='assets/app.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Orbit',
)
