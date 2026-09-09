"""Static checks on the desktop packaging inputs (PyInstaller spec + build/package scripts).

These are cheap guards: they do not run PyInstaller, they only assert the spec still bundles
the resources the frozen app needs at runtime and never excludes a module the app imports.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _excludes_block(spec: str) -> str:
    """Return the concatenated text of every `excludes = [...]` / `excludes += [...]` literal.

    The spec builds the exclude list in several steps (a base literal plus per-platform
    `+=` additions), so a guard that only looked at the first literal would miss a module
    excluded later on.
    """
    matches = re.findall(r"excludes\s*\+?=\s*\[(.*?)\]", spec, re.DOTALL)
    assert matches, "spec has no `excludes = [...]` literal"
    return "\n".join(matches)


def test_spec_and_scripts_exist():
    assert (ROOT / "packaging" / "kuantra.spec").is_file()
    for f in ("icon.icns", "icon.ico", "icon.png"):
        assert (ROOT / "packaging" / "icons" / f).is_file(), f
    for f in ("build_desktop.py", "smoke_desktop.py", "smoke_macos_dmg.py", "run_n05_macos_distribution_preflight.py", "check_provenance.py", "package_macos.sh", "package_windows.sh", "package_linux.sh"):
        assert (ROOT / "scripts" / f).is_file(), f


def test_spec_bundles_frontend_alembic_and_app_data():
    spec = (ROOT / "packaging" / "kuantra.spec").read_text()
    for needle in ('"frontend"', "alembic.ini", '"alembic"', 'collect_data_files("app"', "console=False",
                   "com.kuantra.terminal", "NSHighResolutionCapable"):
        assert needle in spec, needle
    excludes = _excludes_block(spec)
    for forbidden in ("numpy", "pandas", "scipy", "duckdb", "unittest"):
        assert f'"{forbidden}"' not in excludes, forbidden


def test_spec_entry_point_is_desktop_main():
    spec = (ROOT / "packaging" / "kuantra.spec").read_text()
    assert "desktop_main.py" in spec
    assert '"Kuantra Terminal"' in spec


def test_build_and_smoke_scripts_target_host_os_outputs():
    build = (ROOT / "scripts" / "build_desktop.py").read_text()
    smoke = (ROOT / "scripts" / "smoke_desktop.py").read_text()
    assert "kuantra.spec" in build
    assert "--skip-frontend" in build
    assert "Kuantra Terminal.app" in build and "kuantra-terminal" in build
    assert "--smoke" in smoke and "--smoke-report" in smoke
    assert "--executable" in smoke and "--artifact" in smoke and "--appimage" in smoke and "--data-dir" in smoke
    assert "smoke_schema_version" in smoke and "executable_sha256" in smoke
    assert "build_provenance" in smoke and "provenance_status" in smoke
    assert "KUANTRA_DATA_DIR" in smoke and "KUANTRA_GATEWAY_ENABLED" in smoke


def test_package_macos_script_builds_dmg():
    sh = (ROOT / "scripts" / "package_macos.sh").read_text()
    assert "hdiutil create" in sh
    assert "codesign" in sh
    assert ".dmg" in sh
    assert 'KUANTRA_MACOS_SIGNING_MODE:-adhoc' in sh
    assert 'KUANTRA_MACOS_SIGNING_IDENTITY' in sh
    assert '--options runtime' in sh
    assert 'codesign --verify --deep --strict' in sh
    assert 'developer-id' in sh


def test_macos_dmg_smoke_binds_mount_and_native_renderer():
    script = (ROOT / "scripts" / "smoke_macos_dmg.py").read_text()
    for needle in ("-readonly", "-mountpoint", "hdiutil", "wkwebview", "--artifact"):
        assert needle in script


def test_n05_distribution_preflight_is_read_only_and_secretless():
    script = (ROOT / "scripts" / "run_n05_macos_distribution_preflight.py").read_text()
    for needle in (
        "SCHEMA_VERSION = \"N05.macos-distribution.v1\"",
        '"-readonly"',
        '"hdiutil"',
        '"codesign"',
        '"spctl"',
        '"stapler"',
        '"raw_output_recorded": False',
        '"signing_secret_read": False',
    ):
        assert needle in script


def test_macos_migration_contract_is_checked_in():
    script = (ROOT / "scripts" / "macos_migration.py").read_text()
    service = (ROOT / "backend" / "app" / "services" / "macos_migration.py").read_text()
    docs = (ROOT / "docs" / "MACOS_MIGRATION.md").read_text()
    for needle in (
        "create",
        "verify",
        "restore",
        "rebuild-projection",
        "upgrade-schema",
        "--source-data-dir",
        "--target-data-dir",
    ):
        assert needle in script
    for needle in (
        "os_keychain_not_exported",
        "duckdb_excluded_rebuild_from_sqlite",
        "exchange_credentials",
        "rebuild_duckdb_projection",
    ):
        assert needle in service
    assert "Windows-to-macOS" in docs
    assert "no-user-data path" in docs
    assert "machine-local keychain" in docs
