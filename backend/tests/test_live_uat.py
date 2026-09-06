import pytest
from scripts.run_live_uat import KuantraLiveUATRunner

class TestLiveUserAcceptanceTesting:
    """Automated Pytest wrapper for the Kuantra Terminal 5-Scenario UAT Suite."""

    def test_live_uat_scenario_1_in_process_backend(self):
        # Scenario 1 used to spawn the Tauri sidecar and read the KUANTRA_BACKEND_PORT
        # stdout handshake. The pywebview shell hosts FastAPI in-process, so the scenario
        # now asserts the in-process /health contract instead.
        runner = KuantraLiveUATRunner()
        runner.run_scenario_1_in_process_backend()
        assert runner.results[0]["status"] == "PASSED"
        assert runner.results[0]["telemetry"]["health_status"] == "online"

    def test_live_uat_scenario_2_hardware_gpu_swarm(self):
        runner = KuantraLiveUATRunner()
        runner.run_scenario_2_gpu_and_swarm()
        assert runner.results[0]["status"] == "DISABLED"

    def test_live_uat_scenario_3_defai_flash_loan(self):
        runner = KuantraLiveUATRunner()
        runner.run_scenario_3_defai_flash_loan()
        assert runner.results[0]["status"] == "DISABLED"

    def test_live_uat_scenario_4_orderbook_and_fix(self):
        runner = KuantraLiveUATRunner()
        runner.run_scenario_4_orderbook_and_fix()
        assert runner.results[0]["status"] == "PASSED"

    def test_live_uat_scenario_5_biometrics_and_lockout(self):
        runner = KuantraLiveUATRunner()
        runner.run_scenario_5_biometrics_and_lockout()
        assert runner.results[0]["status"] == "DISABLED"
