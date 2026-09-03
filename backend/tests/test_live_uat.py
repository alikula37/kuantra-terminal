import pytest
from scripts.run_live_uat import KuantraLiveUATRunner

class TestLiveUserAcceptanceTesting:
    """Automated Pytest wrapper for Kuantra Terminal v1.1.0-institutional 5-Scenario UAT Suite."""

    # Scenario 1 covered the Tauri sidecar port handshake, which the pywebview shell removed
    # (the UI now calls the backend in-process). scripts/run_live_uat.py still carries the dead
    # scenario and is rewritten with the rest of the release tooling.

    def test_live_uat_scenario_2_hardware_gpu_swarm(self):
        runner = KuantraLiveUATRunner()
        runner.run_scenario_2_gpu_and_swarm()
        assert runner.results[0]["status"] == "PASSED"

    def test_live_uat_scenario_3_defai_flash_loan(self):
        runner = KuantraLiveUATRunner()
        runner.run_scenario_3_defai_flash_loan()
        assert runner.results[0]["status"] == "PASSED"

    def test_live_uat_scenario_4_orderbook_and_fix(self):
        runner = KuantraLiveUATRunner()
        runner.run_scenario_4_orderbook_and_fix()
        assert runner.results[0]["status"] == "PASSED"

    def test_live_uat_scenario_5_biometrics_and_lockout(self):
        runner = KuantraLiveUATRunner()
        runner.run_scenario_5_biometrics_and_lockout()
        assert runner.results[0]["status"] == "PASSED"