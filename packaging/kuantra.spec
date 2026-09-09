# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Kuantra Terminal desktop app (pywebview shell). Run via scripts/build_desktop.py."""
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 - SPECPATH is injected by PyInstaller
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
from app.version import __version__  # noqa: E402

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")
APP_NAME = "Kuantra Terminal"
EXE_NAME = APP_NAME if (IS_MAC or IS_WIN) else "kuantra-terminal"
ICON = os.path.join(ROOT, "packaging", "icons", "icon.icns" if IS_MAC else "icon.ico" if IS_WIN else "icon.png")

datas = [
    (os.path.join(ROOT, "frontend", "dist"), "frontend"),
    (os.path.join(BACKEND, "alembic.ini"), "."),
    (os.path.join(BACKEND, "alembic"), "alembic"),
]
datas += collect_data_files("app", includes=["**/*.json", "**/*.yaml", "**/*.yml", "**/*.sql", "**/*.md", "**/*.txt"])
# The bundled plugin packages have no __init__.py, so collect_submodules("app") never sees them and
# their plugin.py files would be dropped. DynamicPluginManager loads each one through
# spec_from_file_location(manifest_dir/"plugin.py"), so shipping the tree verbatim as data makes the
# frozen app behave exactly like a dev checkout.
datas += [(os.path.join(BACKEND, "app", "plugins"), os.path.join("app", "plugins"))]

hiddenimports = []
for pkg in ["app", "starlette", "fastapi", "uvicorn", "pydantic", "cryptography", "httpx", "anyio",
            "alembic", "sqlalchemy.dialects.sqlite"]:
    hiddenimports += collect_submodules(pkg)
# Imported only through string/plugin indirection, so the analysis never sees them:
#   main            - backend/main.py:create_app(), imported inside BackendRuntime._startup()
#   desktop.*       - imported lazily inside desktop_main.build_app()
#   pydantic_settings, dotenv - app.core.config settings loader
#   uvicorn.loops/protocols/lifecycle - selected by name at runtime
#   duckdb, pandas, numpy     - analytics stack loaded through service factories
hiddenimports += [
    "main",
    "desktop", "desktop.bridge", "desktop.clipboard", "desktop.gateway",
    "desktop.push", "desktop.runtime", "desktop.smoke", "desktop.h07_worker",
    "desktop.g0_g2_worker", "desktop.n03_worker",
    # Narrow diagnostic workload; does not execute source provenance collection.
    "scripts.run_h07_benchmark", "scripts.build_provenance",
    "pydantic_settings", "dotenv",
    "uvicorn.loops.auto", "uvicorn.protocols.http.auto", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "duckdb", "pandas", "numpy",
]
# pywebview picks its GUI backend by importing a platform module by name at runtime.
if IS_MAC:
    hiddenimports += ["webview.platforms.cocoa"]
elif IS_WIN:
    hiddenimports += ["webview.platforms.edgechromium"]
else:
    hiddenimports += [
        "webview.platforms.qt",
        "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebEngineCore", "PyQt6.QtWebChannel", "PyQt6.QtNetwork",
        "qtpy.QtWebEngineWidgets",
    ]

excludes = ["torch", "bleak", "web3", "quickfix", "PIL", "matplotlib", "tkinter", "pytest", "test",
            "alembic.testing", "setuptools", "pkg_resources", "ccxt.pro", "aiohttp.test_utils"]
if not IS_WIN:
    excludes.append("winloop")
if IS_MAC:
    # macOS uses the native cocoa (pywebview/WebKit) backend; Qt would only bloat the bundle.
    excludes += ["PyQt6", "PyQt5", "PySide6", "PySide2", "qtpy"]
elif IS_WIN:
    # Windows production uses WebView2. Keep the Qt diagnostic override out of the production
    # payload; a separate diagnostic build can re-enable it explicitly when needed.
    excludes += ["PyQt6", "PyQt5", "PySide6", "PySide2", "qtpy"]
else:
    # Linux uses the Qt backend (PyQt6 + PyQt6-WebEngine).
    excludes += ["PyQt5", "PySide6", "PySide2"]

a = Analysis(  # noqa: F821
    [os.path.join(BACKEND, "desktop_main.py")],
    pathex=[BACKEND, ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=EXE_NAME,
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=ICON,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=EXE_NAME)  # noqa: F821

if IS_MAC:
    app = BUNDLE(  # noqa: F821
        coll,
        name=f"{APP_NAME}.app",
        icon=ICON,
        bundle_identifier="com.kuantra.terminal",
        version=__version__,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSRequiresAquaSystemAppearance": False,
            "LSApplicationCategoryType": "public.app-category.finance",
        },
    )
