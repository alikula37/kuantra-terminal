from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]


def test_nsis_script_contract():
    nsi = (ROOT / "packaging" / "windows" / "installer.nsi").read_text()
    for needle in ("RequestExecutionLevel user", "$LOCALAPPDATA\\Programs", "taskkill /F /T /IM",
                   '!define EXE_NAME "Kuantra Terminal.exe"', "Section \"Uninstall\"", "${VERSION}"):
        assert needle in nsi, needle


def test_linux_desktop_and_apprun():
    desk = (ROOT / "packaging" / "linux" / "kuantra-terminal.desktop").read_text()
    assert "Exec=kuantra-terminal" in desk and "Icon=kuantra-terminal" in desk and "Categories=" in desk
    apprun = (ROOT / "packaging" / "linux" / "AppRun").read_text()
    assert "PYWEBVIEW_GUI" in apprun and 'exec "$HERE/usr/bin/kuantra-terminal"' in apprun
