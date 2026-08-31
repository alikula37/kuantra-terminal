# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += collect_submodules('app')
hiddenimports += collect_submodules('starlette')
hiddenimports += collect_submodules('fastapi')
hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('pydantic')
hiddenimports += collect_submodules('cryptography')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['duckdb', 'pandas', 'numpy', 'scipy', 'torch', 'bleak', 'web3', 'quickfix', 'PIL', 'matplotlib', 'tkinter', 'pytest', 'unittest', 'doctest', 'test', 'alembic.testing', 'setuptools', 'pkg_resources', 'xmlrpc', 'pydoc', 'curses'],
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
    name='kuantra-backend-x86_64-pc-windows-msvc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
