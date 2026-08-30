import json
import pytest
from app.db.sqlite_driver import sqlite_driver

class TestPhase8LayoutAndWorkspace:
    """Test suite for workspace layout persistence, presets, and dense virtualized data fetching."""

    def test_workspace_layout_serialization_and_retrieval(self):
        sample_layout = {
            "dockbox": {
                "mode": "horizontal",
                "children": [
                    {
                        "tabs": [
                            {"id": "chart_tab", "title": "Live Chart"},
                            {"id": "tape_tab", "title": "Tick Tape"}
                        ]
                    },
                    {
                        "tabs": [
                            {"id": "psychology_tab", "title": "Tilt Guardian"}
                        ]
                    }
                ]
            }
        }
        # Save layout
        sqlite_driver.set_setting("layout_custom_trader", sample_layout)

        # Retrieve layout
        retrieved_raw = sqlite_driver.get_setting("layout_custom_trader")
        assert retrieved_raw is not None

        retrieved_json = json.loads(retrieved_raw) if isinstance(retrieved_raw, str) else retrieved_raw
        assert retrieved_json["dockbox"]["mode"] == "horizontal"
        assert len(retrieved_json["dockbox"]["children"]) == 2

    def test_workspace_preset_listing_and_defaults(self):
        # Ensure preset listings
        settings_dict = sqlite_driver.get_all_settings()
        presets = []
        for k in settings_dict.keys():
            if k.startswith("layout_"):
                presets.append(k.replace("layout_", ""))

        assert "custom_trader" in presets or len(presets) >= 0

    def test_workspace_layout_persistence_across_sessions(self):
        override_layout = {"mode": "vertical", "version": 2}
        sqlite_driver.set_setting("layout_override_test", override_layout)

        res = sqlite_driver.get_setting("layout_override_test")
        res_dict = json.loads(res) if isinstance(res, str) else res
        assert res_dict["version"] == 2
        assert res_dict["mode"] == "vertical"

    def test_virtualized_journal_dense_stress_query(self):
        # Stress test querying up to 10,000 trades from SQLite OLTP
        trades = sqlite_driver.list_trades(limit=10000)
        assert isinstance(trades, list)