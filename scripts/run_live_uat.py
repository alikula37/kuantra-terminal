"""Truth-boundary UAT and system audit runner for Kuantra Terminal.

The runner distinguishes verified core scenarios from intentionally disabled
experimental surfaces. A disabled scenario is evidence that the product did
not fabricate live data, model inference, chain state, or hardware authority.
"""

import os
import sys
import time
import json
from typing import Dict, Any, List

# Add backend directory to sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "backend"))

from fastapi.testclient import TestClient
from app.version import __version__
from main import create_app
from app.services.matching.order_book import global_order_book, LimitOrderBook
from app.services.fix.fix_gateway import fix_session, FIXMessage
from app.services.fix.dma_router import dma_router

class KuantraLiveUATRunner:
    """Truth-boundary UAT scenario executor and audit report generator."""

    def __init__(self):
        self.app = create_app()
        self.client = TestClient(self.app)
        self.results: List[Dict[str, Any]] = []

    def log_scenario(self, scenario_num: int, name: str, status: str, duration_ms: float, metrics: Dict[str, Any]):
        entry = {
            "scenario": f"SCENARIO {scenario_num}",
            "name": name,
            "status": status,
            "duration_ms": round(duration_ms, 2),
            "telemetry": metrics
        }
        self.results.append(entry)
        symbol = "[PASS]" if status == "PASSED" else ("[DISABLED]" if status == "DISABLED" else "[FAIL]")
        print(f"{symbol} SCENARIO {scenario_num}: {name} ({duration_ms:.2f}ms)")
        for k, v in metrics.items():
            print(f"      * {k}: {v}")

    # =========================================================================
    # SCENARIO 1: In-Process Backend Boot & /health Verification
    # =========================================================================
    def run_scenario_1_in_process_backend(self):
        """The pywebview shell hosts FastAPI in-process: no sidecar, no port handshake."""
        t0 = time.perf_counter()

        res_health = self.client.get("/health")
        assert res_health.status_code == 200, f"/health returned {res_health.status_code}"
        health = res_health.json()
        assert health["status"] == "online"
        assert health["version"]

        duration_ms = (time.perf_counter() - t0) * 1000.0
        self.log_scenario(
            scenario_num=1,
            name="In-Process Backend Boot & /health Verification",
            status="PASSED",
            duration_ms=duration_ms,
            metrics={
                "transport": "in-process ASGI (no sidecar subprocess)",
                "health_status": health["status"],
                "backend_version": health["version"],
                "boot_latency_ms": f"{duration_ms:.2f}ms"
            }
        )

    # =========================================================================
    # SCENARIO 2: Local AI Hardware & Swarm Truth Gate
    # =========================================================================
    def run_scenario_2_gpu_and_swarm(self):
        t0 = time.perf_counter()

        # No synthetic GPU/model telemetry is accepted as a production pass.
        res_hw = self.client.get("/api/v1/hardware/gpu-status")
        assert res_hw.status_code == 503
        detail = res_hw.json()["detail"]
        assert detail["status"] == "EXPERIMENTAL_DISABLED"
        assert detail["execution_authority"] is False

        duration_ms = (time.perf_counter() - t0) * 1000.0
        self.log_scenario(
            scenario_num=2,
            name="Local AI Hardware & Swarm Truth Gate",
            status="DISABLED",
            duration_ms=duration_ms,
            metrics={
                "capability": detail["capability"],
                "reason": detail["reason"],
                "execution_authority": detail["execution_authority"],
            }
        )

    # =========================================================================
    # SCENARIO 3: DEX/RPC/DeFAI Truth Gate
    # =========================================================================
    def run_scenario_3_defai_flash_loan(self):
        t0 = time.perf_counter()

        # No static chain state or simulated profit is a production pass.
        res_chains = self.client.get("/api/v1/dex/chains")
        assert res_chains.status_code == 503
        detail = res_chains.json()["detail"]
        assert detail["status"] == "EXPERIMENTAL_DISABLED"
        assert detail["execution_authority"] is False

        duration_ms = (time.perf_counter() - t0) * 1000.0
        self.log_scenario(
            scenario_num=3,
            name="DEX/RPC/DeFAI Truth Gate",
            status="DISABLED",
            duration_ms=duration_ms,
            metrics={
                "capability": detail["capability"],
                "reason": detail["reason"],
                "execution_authority": detail["execution_authority"],
            }
        )

    # =========================================================================
    # SCENARIO 4: Order-flow/L2/FIX Truth Boundary Audit
    # =========================================================================
    def run_scenario_4_orderbook_and_fix(self):
        t0 = time.perf_counter()

        # 1. Fresh runtime must not invent market depth.
        res_snap = self.client.get("/api/v1/orderbook/l2-snapshot?depth=10")
        assert res_snap.status_code == 200
        snap = res_snap.json()
        assert snap["status"] == "NO_DATA"
        assert snap["bids"] == []
        assert snap["asks"] == []
        assert snap["best_bid"] is None
        assert snap["best_ask"] is None

        # 2. Sweep endpoint must refuse to imply a venue fill.
        res_sweep = self.client.post("/api/v1/orderbook/simulate-fill", json={"side": "BUY", "size": 5.0})
        assert res_sweep.status_code == 503
        sweep_data = res_sweep.json()
        assert sweep_data["status"] == "EXPERIMENTAL_DISABLED"
        assert sweep_data["execution_vwap"] is None
        assert sweep_data["filled_size"] == 0.0

        # 3. Local FIX wire helper cannot claim a broker logon.
        res_logon = self.client.post("/api/v1/fix/session/logon")
        assert res_logon.status_code == 503
        logon_data = res_logon.json()
        assert logon_data["status"] == "EXPERIMENTAL_DISABLED"
        assert logon_data["session_state"] == "DISCONNECTED"

        # 4. Order submission must fail closed without a certified transport.
        res_order = self.client.post("/api/v1/fix/order/submit", json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "price": 65000.0,
            "qty": 1.5,
            "order_type": "LIMIT",
            "destination": "INTERNAL_MATCHING_ENGINE"
        })
        assert res_order.status_code == 503
        order_data = res_order.json()
        assert order_data["status"] == "EXPERIMENTAL_DISABLED"
        assert order_data["execution_status"] == "NOT_SUBMITTED"
        assert order_data["filled_size"] == 0.0

        duration_ms = (time.perf_counter() - t0) * 1000.0
        self.log_scenario(
            scenario_num=4,
            name="Order-flow/L2/FIX Truth Boundary Audit",
            status="PASSED",
            duration_ms=duration_ms,
            metrics={
                "l2_status": snap["status"],
                "sweep_status": sweep_data["status"],
                "sweep_fill": sweep_data["filled_size"],
                "fix_session_state": logon_data["session_state"],
                "fix_order_status": order_data["execution_status"],
                "provenance": order_data["provenance"],
            }
        )

    # =========================================================================
    # SCENARIO 5: Biometric Hardware & WebAuthn Truth Gate
    # =========================================================================
    def run_scenario_5_biometrics_and_lockout(self):
        t0 = time.perf_counter()

        # A virtual device, manual telemetry, or length-only signature is not
        # accepted as a production safety control.
        res_conn = self.client.post("/api/v1/biometrics/connect", json={
            "device_id": "POLAR-H10-8849",
            "protocol": "BLE"
        })
        assert res_conn.status_code == 503
        detail = res_conn.json()["detail"]
        assert detail["status"] == "EXPERIMENTAL_DISABLED"
        assert detail["execution_authority"] is False

        duration_ms = (time.perf_counter() - t0) * 1000.0
        self.log_scenario(
            scenario_num=5,
            name="Biometric Hardware & WebAuthn Truth Gate",
            status="DISABLED",
            duration_ms=duration_ms,
            metrics={
                "capability": detail["capability"],
                "reason": detail["reason"],
                "execution_authority": detail["execution_authority"],
            }
        )

    # =========================================================================
    # Execute All Scenarios & Output Audit Report
    # =========================================================================
    def execute_full_uat_suite(self):
        print("\n==================================================================================================")
        print(f"              KUANTRA TERMINAL v{__version__} TRUTH-BOUNDARY UAT SUITE            ")
        print("==================================================================================================")
        print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime())} | Target: Production Engine\n")

        self.run_scenario_1_in_process_backend()
        self.run_scenario_2_gpu_and_swarm()
        self.run_scenario_3_defai_flash_loan()
        self.run_scenario_4_orderbook_and_fix()
        self.run_scenario_5_biometrics_and_lockout()

        total_pass = sum(1 for r in self.results if r["status"] == "PASSED")
        total_count = len(self.results)
        pass_rate = (total_pass / total_count) * 100.0

        print("\n==================================================================================================")
        print(f"                    UAT EXECUTION COMPLETED: {total_pass}/{total_count} SCENARIOS PASSED ({pass_rate:.1f}%)                 ")
        print("==================================================================================================\n")

        # Export only to the ignored evidence area. A generated UAT report is not a
        # release truth source and must not sit at the repository root beside current
        # product documents. An explicit path remains available for local audits.
        audit_artifact_path = os.environ.get(
            "KUANTRA_UAT_REPORT_PATH",
            os.path.join("artifacts", "evidence", "uat", f"UAT_AUDIT_REPORT-v{__version__}.json"),
        )
        if not os.path.isabs(audit_artifact_path):
            audit_artifact_path = os.path.join(ROOT_DIR, audit_artifact_path)
        os.makedirs(os.path.dirname(audit_artifact_path) or ROOT_DIR, exist_ok=True)
        with open(audit_artifact_path, "w", encoding="utf-8") as f:
            json.dump({
                "version": __version__,
                "release_tag": f"v{__version__}",
                "pass_rate_pct": pass_rate,
                "scenarios": self.results
            }, f, indent=2)

        return pass_rate == 100.0

if __name__ == "__main__":
    runner = KuantraLiveUATRunner()
    success = runner.execute_full_uat_suite()
    sys.exit(0 if success else 1)
