"""H05 supply-chain, deterministic inventory and secret-boundary contracts."""

import json
from pathlib import Path

from scripts.supply_chain_audit import (
    build_cyclonedx_bom,
    build_audit_report,
    scan_file,
    scan_text,
    validate_lock_contract,
)


ROOT = Path(__file__).resolve().parents[2]


def test_locked_dependency_contract_is_current():
    assert validate_lock_contract(ROOT) == []


def test_frontend_lock_drift_is_fail_closed(tmp_path):
    package_root = tmp_path / "frontend"
    package_root.mkdir()
    (package_root / "package.json").write_text(
        json.dumps(
            {
                "name": "fixture",
                "version": "1.0.0",
                "dependencies": {"react": "^18.3.1"},
                "devDependencies": {},
            }
        ),
        encoding="utf-8",
    )
    (package_root / "package-lock.json").write_text(
        json.dumps(
            {
                "name": "fixture",
                "version": "1.0.0",
                "lockfileVersion": 3,
                "packages": {
                    "": {
                        "name": "fixture",
                        "version": "1.0.0",
                        "dependencies": {"react": "^17.0.0"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    errors = validate_lock_contract(tmp_path)

    assert any("frontend dependency spec drift" in error for error in errors)


def test_cyclonedx_inventory_is_deterministic_and_preserves_provenance():
    first = build_cyclonedx_bom(ROOT)
    second = build_cyclonedx_bom(ROOT)

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["bomFormat"] == "CycloneDX"
    assert first["specVersion"] == "1.5"
    components = first["components"]
    assert components
    assert len({component["bom-ref"] for component in components}) == len(components)
    assert any(
        property_["name"] == "kuantra:dependency-scope"
        and property_["value"] in {"direct", "transitive"}
        for component in components
        for property_ in component["properties"]
    )
    assert first["metadata"]["properties"]


def test_secret_canaries_are_detected_without_treating_placeholders_as_secrets():
    findings = scan_text(
        "api_key='AKIAIOSFODNN7EXAMPLE'\n"
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.very-long-token-value\n"
        "-----BEGIN RSA PRIVATE KEY-----\nsecret-body\n-----END RSA PRIVATE KEY-----\n",
        source_name="fixture.py",
    )
    assert {finding["kind"] for finding in findings} >= {
        "cloud-access-key",
        "bearer-token",
        "private-key",
    }
    assert scan_text("api_key='test-placeholder'", source_name="fixture.py") == []


def test_clean_release_source_and_artifact_have_no_secret_findings(tmp_path):
    assert scan_file(ROOT / "backend" / "app" / "cli.py") == []
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"clean packaged bytes")
    assert scan_file(artifact) == []


def test_audit_report_keeps_license_owner_review_separate_from_scan_pass():
    report = build_audit_report(ROOT)

    assert report["secret_scan"]["status"] == "PASS"
    assert report["lock_contract"]["status"] == "PASS"
    assert report["license_review"]["status"] == "OWNER_DECISION_REQUIRED"
    assert report["release_gate"]["status"] == "OWNER_REVIEW_REQUIRED"
