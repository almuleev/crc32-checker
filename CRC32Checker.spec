# Build a single portable Windows executable with its Python and Tcl/Tk runtime.
import sys

if sys.version_info[:3] != (3, 14, 4) or sys.maxsize <= 2**32:
    raise RuntimeError('Portable builds require Python 3.14.4 x64 with Tcl/Tk 8.6.')

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
