"""
Strategy Playbook & Discipline Engine for Kuantra Terminal.
Provides institutional playbook criteria checklists, discipline scoring, and execution auditing.
"""

from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
import numpy as np
from app.db.sqlite_driver import sqlite_driver
from app.quant.quant_engine import quant_engine

class PlaybookService:
    """Manages strategy playbooks, rule checklists, and calculates execution discipline scores."""

    def __init__(self):
        self._init_db()
        self._seed_default_playbooks()

    def _init_db(self):
        with sqlite_driver.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript("""
                CREATE TABLE IF NOT EXISTS playbooks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    win_rate_target REAL DEFAULT 65.0,
                    rr_target REAL DEFAULT 2.5,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS playbook_rules (
                    id TEXT PRIMARY KEY,
                    playbook_id TEXT NOT NULL,
                    rule_text TEXT NOT NULL,
                    is_mandatory INTEGER DEFAULT 0,
                    weight REAL DEFAULT 1.0,
                    FOREIGN KEY (playbook_id) REFERENCES playbooks(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS trade_rule_checks (
                    trade_id TEXT NOT NULL,
                    playbook_id TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    is_checked INTEGER NOT NULL,
                    PRIMARY KEY (trade_id, rule_id)
                );
            """)
            conn.commit()

    def _seed_default_playbooks(self):
        """Seeds standard institutional playbooks if table is empty."""
        with sqlite_driver.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM playbooks")
            count = cursor.fetchone()["count"]
            if count == 0:
                self.create_playbook(
                    title="Liquidity Sweep & Order Block Reversal",
                    description="Institutional smart money setup catching stops above/below key swing levels with MSS confirmation.",
                    win_rate_target=68.0,
                    rr_target=2.75,
                    rules=[
                        {"rule_text": "Higher timeframe (4h/1D) key level swept and rejected", "is_mandatory": True, "weight": 2.0},
                        {"rule_text": "Market structure shift (MSS) confirmed on 5m execution timeframe", "is_mandatory": True, "weight": 2.0},
                        {"rule_text": "Fair Value Gap (FVG) or optimal trade entry (OTE) tap on entry", "is_mandatory": False, "weight": 1.5},
                        {"rule_text": "Relative Volume (RVOL) > 1.5x on reversal displacement", "is_mandatory": False, "weight": 1.0},
                        {"rule_text": "Stop loss placed strictly beyond swing invalidation point", "is_mandatory": True, "weight": 2.5}
                    ]
                )
                self.create_playbook(
                    title="High-Momentum Breakout & Retest",
                    description="Trend continuation strategy capturing clean compression breaks above major volume nodes.",
                    win_rate_target=62.0,
                    rr_target=2.5,
                    rules=[
                        {"rule_text": "Consolidation base duration >= 2 hours with volatility compression", "is_mandatory": True, "weight": 1.5},
                        {"rule_text": "Breakout bar closes clearly beyond resistance with volume surge", "is_mandatory": True, "weight": 2.0},
                        {"rule_text": "First retest of broken level holds with lower timeframe wick rejection", "is_mandatory": False, "weight": 1.5},
                        {"rule_text": "Pre-defined Take Profit at least 2.5x initial stop risk", "is_mandatory": True, "weight": 2.0}
                    ]
                )

    def create_playbook(
        self,
        title: str,
        description: str,
        win_rate_target: float = 65.0,
        rr_target: float = 2.5,
        rules: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        playbook_id = f"PB-{uuid.uuid4().hex[:6].upper()}"

        with sqlite_driver.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO playbooks (id, title, description, win_rate_target, rr_target, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (playbook_id, title, description, float(win_rate_target), float(rr_target), now, now))

            if rules:
                for r in rules:
                    rule_id = f"RUL-{uuid.uuid4().hex[:6].upper()}"
                    cursor.execute("""
                        INSERT INTO playbook_rules (id, playbook_id, rule_text, is_mandatory, weight)
                        VALUES (?, ?, ?, ?, ?)
                    """, (rule_id, playbook_id, r["rule_text"], 1 if r.get("is_mandatory") else 0, float(r.get("weight", 1.0))))
            conn.commit()

        return self.get_playbook(playbook_id)

    def get_playbook(self, playbook_id: str) -> Optional[Dict[str, Any]]:
        with sqlite_driver.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM playbooks WHERE id = ?", (playbook_id,))
            pb_row = cursor.fetchone()
            if not pb_row:
                return None

            cursor.execute("SELECT * FROM playbook_rules WHERE playbook_id = ?", (playbook_id,))
            rules = [dict(r) for r in cursor.fetchall()]

            # Calculate performance stats for this playbook
            cursor.execute("""
                SELECT t.* FROM trades t
                WHERE t.notes LIKE ? OR t.notes LIKE ?
            """, (f"%{playbook_id}%", f"%{pb_row['title']}%"))
            trades = [dict(t) for t in cursor.fetchall()]

            pnls = [float(t["pnl"]) for t in trades if t.get("pnl") is not None]
            r_mults = [float(t["r_multiple"]) for t in trades if t.get("r_multiple") is not None]

            scorecard = quant_engine.calculate_full_performance_suite(pnls, r_multiples=r_mults if len(r_mults) == len(pnls) else None)

            return {
                **dict(pb_row),
                "rules": rules,
                "trades_count": len(trades),
                "performance": scorecard
            }

    def list_playbooks(self) -> List[Dict[str, Any]]:
        with sqlite_driver.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM playbooks ORDER BY created_at ASC")
            rows = cursor.fetchall()
            return [self.get_playbook(r["id"]) for r in rows if self.get_playbook(r["id"])]

    @staticmethod
    def calculate_discipline_score(
        rules: List[Dict[str, Any]],
        checked_rule_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Discipline Score = (Sum of Checked Weights / Sum of Total Weights) * 100
        Flags mandatory rule violations if any mandatory rule is unchecked.
        """
        if not rules:
            return {"score": 100.0, "mandatory_violation": False, "passed_rules": 0, "total_rules": 0}

        total_weight = sum(float(r.get("weight", 1.0)) for r in rules)
        checked_set = set(checked_rule_ids)

        checked_weight = sum(float(r.get("weight", 1.0)) for r in rules if r["id"] in checked_set)
        
        # Mandatory violations check
        mandatory_violation = any(
            bool(r.get("is_mandatory")) and (r["id"] not in checked_set)
            for r in rules
        )

        score = (checked_weight / total_weight) * 100.0 if total_weight > 0 else 0.0

        return {
            "score": round(score, 2),
            "mandatory_violation": mandatory_violation,
            "checked_weight": round(checked_weight, 2),
            "total_weight": round(total_weight, 2),
            "passed_rules": len(checked_set),
            "total_rules": len(rules)
        }

    def audit_trade_discipline(
        self,
        trade_id: str,
        playbook_id: str,
        checked_rule_ids: List[str]
    ) -> Dict[str, Any]:
        """Records audit checklist for a trade and returns calculated discipline score."""
        pb = self.get_playbook(playbook_id)
        if not pb:
            raise ValueError(f"Playbook {playbook_id} not found")

        rules = pb["rules"]
        audit_result = self.calculate_discipline_score(rules, checked_rule_ids)

        with sqlite_driver.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trade_rule_checks WHERE trade_id = ?", (trade_id,))
            for r in rules:
                is_chk = 1 if r["id"] in checked_rule_ids else 0
                cursor.execute("""
                    INSERT INTO trade_rule_checks (trade_id, playbook_id, rule_id, is_checked)
                    VALUES (?, ?, ?, ?)
                """, (trade_id, playbook_id, r["id"], is_chk))
            conn.commit()

        return {
            "trade_id": trade_id,
            "playbook_id": playbook_id,
            "playbook_title": pb["title"],
            "discipline_score": audit_result["score"],
            "mandatory_violation": audit_result["mandatory_violation"],
            "details": audit_result
        }

playbook_service = PlaybookService()