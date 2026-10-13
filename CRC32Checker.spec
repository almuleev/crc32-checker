# Build a single portable Windows executable with its Python and Tcl/Tk runtime.
a = Analysis(
    ['crc32_checker.py'],
    pathex=[],
    binaries=[],
    datas=[('LICENSE', '.'), ('THIRD_PARTY_NOTICES.md', '.'),
           ('licenses', 'licenses'), ('assets/icon.ico', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CRC32Checker',
    icon='assets/icon.ico',
    version='version_info.txt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    runtime_tmpdir=None,
    uac_admin=False,
)
