"""Portable structural checks for the CI and release truth/safety gates."""

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
REQUIRED_GATES = [
    "Install Python dependencies",
    "Compile Python sources",
    "Verify release truth contract",
    "Run full backend test suite",
    "Install frontend dependencies",
    "Audit frontend dependencies",
    "Run frontend tests",
    "Build frontend",
    "Build desktop app",
    "Smoke test desktop app",
]


def load_workflow(name: str) -> str:
    path = WORKFLOW_DIR / name
    return path.read_text(encoding="utf-8")


def job_block(raw: str, job_name: str) -> str:
    match = re.search(
        rf"^  {re.escape(job_name)}:\n(?P<body>.*?)(?=^  [A-Za-z][\w-]*:\n|\Z)",
        raw,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match, f"workflow does not contain job {job_name!r}"
    return match.group("body")


def step_names(job: str) -> list[str]:
    return re.findall(r"^      - name: ([^\n]+)$", job, flags=re.MULTILINE)


def assert_gate_order(job: str, required_gates: list[str]) -> None:
    names = step_names(job)
    indices = [names.index(gate) for gate in required_gates]
    assert indices == sorted(indices)


def assert_isolated_data_dir(job: str) -> None:
    assert "Initialize isolated data directory" in step_names(job)
    assert "KUANTRA_DATA_DIR=${{ runner.temp }}/" in job
    assert '>> "$GITHUB_ENV"' in job
    # The runner context is available to steps, not while job-level env is evaluated.
    assert not re.search(
        r"^    env:\n      KUANTRA_DATA_DIR:\s*\$\{\{ runner\.temp \}\}/",
        job,
        flags=re.MULTILINE,
    )


def assert_frontend_commands_are_ordered(job: str) -> None:
    commands = job
    required_commands = [
        "npm --prefix frontend ci",
        "npm --prefix frontend audit --audit-level=moderate",
        "npm --prefix frontend test",
        "npm --prefix frontend run build",
    ]
    indices = [commands.index(command) for command in required_commands]
    assert indices == sorted(indices)


def test_ci_workflow_enforces_portable_truth_and_safety_gates():
    raw = load_workflow("ci.yml")
    assert "branches: [ main, 'codex/**', 'feat/**' ]" in raw
    assert "pull_request:\n    branches: [ main ]" in raw

    job = job_block(raw, "test-and-build")
    assert_isolated_data_dir(job)
    assert_gate_order(job, REQUIRED_GATES)
    assert_frontend_commands_are_ordered(job)
    assert "npm --prefix frontend audit --audit-level=moderate" in raw
    assert "--force" not in raw
    assert "audit ignore" not in raw.lower()


def test_release_workflow_gates_packaging_and_publish_on_all_matrix_jobs():
    raw = load_workflow("release.yml")
    package_job = job_block(raw, "build-and-package")
    assert_isolated_data_dir(package_job)
    assert_gate_order(package_job, REQUIRED_GATES)
    assert_frontend_commands_are_ordered(package_job)
    names = step_names(package_job)
    assert names.index("Smoke test desktop app") < names.index("Package")
    publish_job = job_block(raw, "publish-release")
    assert re.search(r"^    needs:\s*build-and-package$", publish_job, flags=re.MULTILINE)
    assert "npm --prefix frontend audit --audit-level=moderate" in raw
    assert "--force" not in raw
    assert "audit ignore" not in raw.lower()
