import pytest
from app.services.p2p.mesh_node import p2p_mesh_node, P2PMeshNode
from app.services.p2p.copy_engine import copy_trading_engine, ZeroKnowledgeCopyEngine
from app.services.execution.multi_account_router import multi_account_allocator, MultiAccountRiskAllocator
from app.services.biometrics.watch_bridge import biometric_watch_bridge

class TestPhase14P2PCopyAndMultiAccount:
    """Test suite for Encrypted P2P Mesh Network, Zero-Knowledge Copy Trading, and Multi-Account Risk Routing."""

    @pytest.fixture
    def compliant_account(self, monkeypatch):
        """Keep multi-account routing tests independent from persistent journal state."""
        compliant = {
            "overall_status": "COMPLIANT",
            "daily_loss_pct_of_account": 0.0,
            "daily_loss_limit_pct": 5.0,
            "rules": [{"rule": "Daily Max Loss", "utilization_pct": 0.0}],
        }
        monkeypatch.setattr(
            "app.services.execution.risk_interceptor.compliance_engine.evaluate_compliance",
            lambda *args, **kwargs: compliant,
        )
        monkeypatch.setattr(
            "app.quant.risk_guard.compliance_engine.evaluate_compliance",
            lambda *args, **kwargs: compliant,
        )

    def test_p2p_mesh_identity_and_noise_packet_encryption(self):
        node = P2PMeshNode(node_name="TestNode-01")
        assert node.node_id.startswith("12D3KooW")
        assert len(node.pubkey) == 64

        # Encrypt packet
        shared_key = "test-session-secret-key-123"
        payload = {"symbol": "BTCUSDT", "side": "BUY", "price": 64800.0}
        enc_pkt = node.encrypt_packet(payload, shared_key)
        assert "ciphertext" in enc_pkt
        assert "auth_tag" in enc_pkt

        # Decrypt packet
        decrypted = node.decrypt_packet(enc_pkt, shared_key)
        assert decrypted["symbol"] == "BTCUSDT"
        assert decrypted["price"] == 64800.0

        # Tampering detection
        tampered_pkt = dict(enc_pkt)
        tampered_pkt["auth_tag"] = "invalid_tampered_tag_hex"
        with pytest.raises(ValueError, match="Authentication Failed"):
            node.decrypt_packet(tampered_pkt, shared_key)

    def test_p2p_mesh_peer_discovery_and_broadcast(self):
        node = P2PMeshNode(node_name="TestNode-02")
        node.add_peer(
            peer_id="12D3KooW-Slave01",
            node_name="Slave-01",
            pubkey="pubkey-slave-01",
            endpoint="10.0.0.5:9001",
            role="FOLLOWER"
        )
        node.add_peer(
            peer_id="12D3KooW-Slave02",
            node_name="Slave-02",
            pubkey="pubkey-slave-02",
            endpoint="10.0.0.6:9002",
            role="FOLLOWER"
        )
        node.add_peer(
            peer_id="12D3KooW-Slave03",
            node_name="Slave-03",
            pubkey="pubkey-slave-03",
            endpoint="10.0.0.7:9003",
            role="FOLLOWER"
        )
        assert len(node.peers) >= 3
        st = node.get_mesh_status()
        assert st["is_active"] is True
        assert st["peers_count"] >= 3

        bc = node.broadcast_signal({"signal_id": "SIG-TEST", "symbol": "XAUUSD"})
        assert bc["status"] == "BROADCAST_SUCCESS"
        assert bc["peers_reached"] >= 3

    def test_zero_knowledge_copy_signal_signing_and_verification(self):
        engine = ZeroKnowledgeCopyEngine()
        sig = engine.create_master_signal(
            symbol="BTCUSDT",
            side="BUY",
            entry_price=65000.0,
            stop_loss=64000.0,
            take_profit=68000.0,
            risk_pct=1.0
        )
        assert sig["signal_id"].startswith("SIG-BTCUSDT")
        assert len(sig["signature"]) == 64
        assert engine.verify_signal(sig) is True

        # Invalid signature
        invalid_sig = dict(sig)
        invalid_sig["signature"] = "short"
        assert engine.verify_signal(invalid_sig) is False

    def test_dynamic_follower_equity_lot_sizing(self):
        engine = ZeroKnowledgeCopyEngine()
        # $1,000 price risk per unit ($65,000 -> $64,000)
        signal = {
            "symbol": "BTCUSDT",
            "entry_price": 65000.0,
            "stop_loss": 64000.0,
            "risk_pct": 1.0 # 1%
        }

        # Follower A: $50k equity -> $500 risk -> 0.50 lots
        size_a = engine.calculate_follower_lot_size(signal, follower_equity=50000.0)
        assert size_a == 0.50

        # Follower B: $100k equity -> $1,000 risk -> 1.00 lots
        size_b = engine.calculate_follower_lot_size(signal, follower_equity=100000.0)
        assert size_b == 1.00

        # Follower C: $250k equity -> $2,500 risk -> 2.50 lots
        size_c = engine.calculate_follower_lot_size(signal, follower_equity=250000.0)
        assert size_c == 2.50

    def test_multi_account_fanout_routing_and_drawdown_gating(self, compliant_account):
        allocator = MultiAccountRiskAllocator()
        biometric_watch_bridge.update_telemetry(bpm=58.0, hrv=85.0) # Calm state

        # 1. Successful fanout across active accounts
        fanout_res = allocator.fanout_order({
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": 1.0,
            "price": 64800.0
        })
        assert fanout_res["status"] == "FANOUT_COMPLETED"
        assert fanout_res["total_allocated_lots"] > 0
        assert len(fanout_res["sub_account_results"]) == 3

        # 2. Drawdown breached account is blocked while compliant accounts pass
        allocator.update_account("ACC-FTMO-100K", {"current_daily_loss": 6000.0}) # Breached $5000 limit
        gated_res = allocator.fanout_order({
            "symbol": "BTCUSDT",
            "side": "BUY",
            "qty": 1.0,
            "price": 64800.0
        })
        ftmo_status = next(r for r in gated_res["sub_account_results"] if r["account_id"] == "ACC-FTMO-100K")
        assert ftmo_status["status"] == "BLOCKED_DRAWDOWN_LIMIT"
        assert "daily loss limit breached" in ftmo_status["reason"]

        # Reset account
        allocator.update_account("ACC-FTMO-100K", {"current_daily_loss": 850.0})
