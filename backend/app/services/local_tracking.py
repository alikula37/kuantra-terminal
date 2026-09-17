"""Local quote-driven tracking. Never writes external fills or broker orders.

PositionProjectionUpdated events carry versioned local-only snapshots. The new
table is a disposable projection, not a new account ledger or source schema.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext

from app.core.position_math import instrument_unit_basis
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository, canonical_json


class TrackingConflict(ValueError):
    pass


class TrackingUnsupported(ValueError):
    """The instrument cannot support a monetary local tracking plan."""


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def timestamp(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Provider timestamp must have timezone")
    return parsed.astimezone(timezone.utc)


def decimal(value, *, positive=True):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid decimal") from exc
    if not result.is_finite() or abs(result) > Decimal("1e30") or (positive and result <= 0):
        raise ValueError("Invalid decimal range")
    return result


def number(value):
    return format(value, "f").rstrip("0").rstrip(".") if "." in format(value, "f") else format(value, "f")


def project_tracking_event(conn, event):
    if event.get("event_type") != "PositionProjectionUpdated":
        return None
    payload = event.get("normalized_payload")
    if payload is None:
        payload = json.loads(event["normalized_payload_json"])
    if not isinstance(payload, dict) or "local_tracking" not in payload:
        return None
    state = payload["local_tracking"]
    validate_snapshot(state)
    if event["correlation_id"] != state["trade_id"] or event["venue"] != "local-journal":
        raise ValueError("Tracking evidence identity mismatch")
    if conn is not None:
        conn.execute(
            "INSERT INTO local_tracking_projections VALUES (?, ?, ?, ?) "
            "ON CONFLICT(trade_id) DO UPDATE SET snapshot_json=excluded.snapshot_json, "
            "source_event_id=excluded.source_event_id, source_event_hash=excluded.source_event_hash",
            (state["trade_id"], canonical_json(state), event["event_id"], event["event_hash"]),
        )
    return state


def validate_snapshot(state):
    if not isinstance(state, dict) or state.get("version") != 1 or state.get("basis") != "LOCAL_ESTIMATE":
        raise ValueError("Unsupported tracking snapshot")
    if type(state.get("revision")) is not int or state["revision"] < 1:
        raise ValueError("Invalid tracking revision")
    initial = decimal(state["initial_qty"])
    remaining = decimal(state["remaining_qty"], positive=False)
    closures = state["closures"]
    if not isinstance(closures, list) or not 0 <= remaining <= initial:
        raise ValueError("Invalid remaining quantity")
    if sum((decimal(c["qty"]) for c in closures), Decimal(0)) + remaining != initial:
        raise ValueError("Tracking quantity mismatch")
    if len(state["targets"]) > 3 or state["side"] not in {"BUY", "SELL", "LONG", "SHORT"}:
        raise ValueError("Invalid tracking targets or side")
    decimal(state["entry_price"])
    decimal(state["gross_pnl"], positive=False)
    timestamp(state["armed_at"])
    if type(state.get("enabled")) is not bool:
        raise ValueError("Invalid tracking enabled flag")
    long = state["side"] in {"BUY", "LONG"}
    entry = decimal(state["entry_price"])
    previous = entry
    total = Decimal(0)
    for index, target in enumerate(state["targets"]):
        price, percent = decimal(target["price"]), decimal(target["percent"])
        if target["id"] != f"TP{index + 1}" or percent > 100 or (long and price <= previous) or (not long and price >= previous):
            raise ValueError("Invalid canonical target")
        previous = price
        total += percent
    if state["targets"] and total != 100:
        raise ValueError("Invalid canonical allocation")
    if state["stop_loss"] is not None:
        stop = decimal(state["stop_loss"])
        if (long and stop >= entry) or (not long and stop <= entry):
            raise ValueError("Invalid canonical stop")
    seen = set()
    gross = Decimal(0)
    usd_notional = str(state.get("qty_unit") or "BASE").upper() == "USD"
    if usd_notional and entry == 0:
        raise ValueError("Invalid USD value basis entry")
    for closure in closures:
        if closure["target_id"] in seen or closure["basis"] != "LOCAL_ESTIMATE":
            raise ValueError("Duplicate or invalid local closure")
        seen.add(closure["target_id"])
        timestamp(closure["observed_at"])
        if closure["target_id"] not in {"TP1", "TP2", "TP3", "SL", "MANUAL"}:
            raise ValueError("Unsupported close target")
        with localcontext() as ctx:
            ctx.prec = 60
            move = decimal(closure["price"]) - entry
            if usd_notional:
                expected = move / entry * decimal(closure["qty"]) * (1 if long else -1)
            else:
                expected = move * decimal(closure["qty"]) * (1 if long else -1)
            if expected != decimal(closure["gross_pnl"], positive=False):
                raise ValueError("Invalid canonical gross result")
            gross += expected
    if gross != decimal(state["gross_pnl"], positive=False):
        raise ValueError("Gross result mismatch")


class LocalTrackingService:
    def __init__(self, driver, catalog=None):
        self.driver = driver
        self.ledger = EvidenceLedgerRepository(driver.db_path)
        self._schema_cookie = None
        if catalog is None:
            from app.services.market_data.instrument_catalog import InstrumentCatalog

            catalog = InstrumentCatalog(db_path=driver.db_path)
        self.catalog = catalog

    def _verified(self):
        with self.driver.get_connection() as conn:
            cookie = conn.execute("PRAGMA schema_version").fetchone()[0]
        # The append-tail cache relies on immutable-ledger guards. A schema
        # change (including dropping/replacing those guards) invalidates that
        # assumption and requires a fresh full verification.
        if cookie != self._schema_cookie:
            self.ledger.close()
            self._schema_cookie = cookie
        if not self.ledger.verify_chain(account_id="local-journal")["valid"]:
            raise ValueError("Tracking evidence chain invalid")

    @staticmethod
    def _load(conn, trade_id):
        # Canonical lookup also recovers a missing/stale disposable projection.
        rows = conn.execute(
            "SELECT * FROM evidence_events WHERE correlation_id=? AND account_id='local-journal' "
            "AND venue='local-journal' AND event_type='PositionProjectionUpdated' "
            "ORDER BY chain_date_utc, chain_sequence", (trade_id,),
        )
        latest, event_id, reset_count = None, None, 0
        for row in rows:
            try:
                payload = json.loads(row["normalized_payload_json"])
            except (TypeError, json.JSONDecodeError):
                payload = {}
            action = payload.get("action") if isinstance(payload, dict) else None
            state = project_tracking_event(None, dict(row))
            if state is not None:
                if action == "PLAN_RESET":
                    # A reset is only written when the previous plan has no
                    # closures, so it starts a clean lineage without touching
                    # any close evidence.
                    reset_count += 1
                    latest, event_id = state, row["event_id"]
                    continue
                if state["revision"] != (latest["revision"] + 1 if latest else 1) or row["causation_id"] != event_id:
                    raise ValueError("Broken tracking revision lineage")
                if latest and (state["closures"][:len(latest["closures"])] != latest["closures"]
                    or any(state[k] != latest[k] for k in ("initial_qty", "entry_price", "side", "symbol"))):
                    raise ValueError("Tracking history was changed")
                latest, event_id = state, row["event_id"]
        return latest, event_id, reset_count

    def get(self, trade_id):
        self._verified()
        with self.driver.get_connection() as conn:
            state, _, _ = self._load(conn, trade_id)
            return state

    def history(self, trade_id):
        self._verified()
        with self.driver.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM evidence_events WHERE correlation_id=? AND account_id='local-journal' "
                "AND venue='local-journal' AND event_type='PositionProjectionUpdated' "
                "ORDER BY chain_date_utc, chain_sequence", (trade_id,),
            ).fetchall()
            return [{"event_id": row["event_id"], "event_hash": row["event_hash"],
                     "state": state} for row in rows
                    if (state := project_tracking_event(None, dict(row))) is not None]

    def list(self):
        self._verified()
        with self.driver.get_connection() as conn:
            ids = conn.execute(
                "SELECT DISTINCT correlation_id FROM evidence_events WHERE account_id='local-journal' "
                "AND event_type='PositionProjectionUpdated' AND venue='local-journal'"
            ).fetchall()
            results = []
            for row in ids:
                state, _, _ = self._load(conn, row[0])
                trade = conn.execute("SELECT * FROM trades WHERE id=?", (row[0],)).fetchone()
                if state:
                    state = deepcopy(state)
                    state["external_status"] = trade["status"] if trade else "UNKNOWN"
                    if trade and (trade["symbol"] != state["symbol"] or trade["side"] != state["side"]
                        or decimal(trade["entry_price"]) != decimal(state["entry_price"])
                        or decimal(trade["qty"]) != decimal(state["initial_qty"])):
                        state["external_status"] = "CORRECTED"
                    if trade and self._unit_verified(trade):
                        state["unit_status"] = (
                            "USD_NOTIONAL"
                            if str(trade["qty_unit"] or "").upper() == "USD"
                            else "BASE_UNIT"
                        )
                    else:
                        state["unit_status"] = "UNVERIFIED"
                    results.append(state)
            return results

    def _save(self, conn, state, action, previous_event=None, observation=None, reset_index=0):
        validate_snapshot(state)
        if action == "PLAN_RESET":
            idempotency_key = f"local-tracking:{state['trade_id']}:reset:{reset_index}:{state['revision']}"
        else:
            idempotency_key = f"local-tracking:{state['trade_id']}:{state['revision']}"
        event = self.ledger.append_event_in_transaction(
            conn, event_type="PositionProjectionUpdated", account_id="local-journal", venue="local-journal",
            idempotency_key=idempotency_key,
            correlation_id=state["trade_id"], causation_id=previous_event,
            normalized_payload={"local_tracking": state, "action": action, "observation": observation},
            occurred_at=now_utc(), schema_version="1", adapter_version="local-tracking-v1",
            provenance={"source": "local_tracking", "basis": "LOCAL_ESTIMATE", "broker_execution": False},
        )
        self.driver._notify_transaction_hook("after_local_tracking_event", conn)
        project_tracking_event(conn, event)
        self.driver._notify_transaction_hook("after_local_tracking_projection", conn)
        return state

    @staticmethod
    def _row_value(row, key):
        try:
            return row[key]
        except (KeyError, IndexError):
            return None

    def _unit_verified(self, trade) -> bool:
        """Base unit from the server-verified catalog or an explicit declaration.

        A plan's provider label is client-supplied and is not verification.  The
        backend's own provider-instrument lookup (or the user's ``qty_unit=BASE``
        declaration) is required before monetary close evidence can be produced.
        """

        symbol = self._row_value(trade, "symbol")
        try:
            server_verified = bool(self.catalog.is_verified(str(symbol or "")))
        except Exception:  # noqa: BLE001 - verification must never block tracking reads
            server_verified = False
        return instrument_unit_basis(
            symbol,
            qty_unit=self._row_value(trade, "qty_unit"),
            server_verified=server_verified,
        )["contract_size"] in {"BASE_UNIT", "USD_NOTIONAL"}

    def edit_in_transaction(self, conn, trade, plan, expected_revision=0, reset=False):
        if not self._unit_verified(trade):
            raise TrackingUnsupported(
                "Local tracking needs an explicit unit declaration "
                "(a USD position value or qty_unit=BASE); neither is recorded for this symbol."
            )
        old, event_id, reset_count = self._load(conn, trade["id"])
        old_revision = old["revision"] if old else 0
        if expected_revision is not None and old_revision != expected_revision:
            raise TrackingConflict("Tracking plan changed; reload before saving")
        if trade["status"] != "OPEN" or (old and decimal(old["remaining_qty"], positive=False) == 0):
            raise TrackingConflict("Tracking is already closed or canceled")
        if reset:
            # Correcting quantity/entry is only safe before any close evidence
            # exists.  After that the plan lineage is immutable.
            if old and old["closures"]:
                raise TrackingConflict("Cannot reset tracking after a partial close")
        elif old and any(str(trade[k]) != str(old[k]) for k in ("symbol", "side")):
            raise TrackingConflict("External trade identity changed")
        state = deepcopy(old) if old and not reset else {
            "version": 1, "basis": "LOCAL_ESTIMATE", "trade_id": trade["id"],
            "symbol": trade["symbol"], "side": trade["side"],
            "entry_price": number(decimal(trade["entry_price"])),
            "initial_qty": number(decimal(trade["qty"])), "remaining_qty": number(decimal(trade["qty"])),
            "gross_pnl": "0", "closures": [], "targets": [],
            "qty_unit": "USD" if str(trade.get("qty_unit") or "").upper() == "USD" else "BASE",
        }
        if type(plan.get("enabled", True)) is not bool:
            raise ValueError("Invalid enabled flag")
        state["enabled"] = plan.get("enabled", True)
        source = plan.get("source_id")
        symbol = plan.get("source_symbol")
        if source is not None and source not in {"binance_public", "bybit_public", "yahoo_public", "stooq_public", "biquote_public"}:
            raise ValueError("Unsupported quote source")
        if bool(source) != bool(symbol) or (symbol and (len(symbol) > 128 or any(ord(c) < 32 for c in symbol))):
            raise ValueError("Invalid quote identity")
        if old and old["closures"] and (source, symbol) != (old["source_id"], old["source_symbol"]):
            raise TrackingConflict("Cannot change source after partial close")
        state.update(source_id=source, source_symbol=symbol)
        entry = decimal(state["entry_price"])
        is_long = state["side"] in {"BUY", "LONG"}
        stop = plan.get("stop_loss")
        if stop is not None:
            stop = decimal(stop)
            if (is_long and stop >= entry) or (not is_long and stop <= entry):
                raise ValueError("Stop loss must be on loss side of entry")
        state["stop_loss"] = number(stop) if stop is not None else None
        targets = plan.get("targets", [])
        if not isinstance(targets, list) or len(targets) > 3:
            raise ValueError("At most three targets")
        normalized = []
        previous = entry
        for index, target in enumerate(targets):
            price, percent = decimal(target["price"]), decimal(target["percent"])
            if percent > 100 or (is_long and price <= previous) or (not is_long and price >= previous):
                raise ValueError("Invalid target order or percent")
            normalized.append({"id": f"TP{index + 1}", "price": number(price), "percent": number(percent)})
            previous = price
        completed_ids = {c["target_id"] for c in state["closures"]}
        for target in state["targets"]:
            if target["id"] in completed_ids and target not in normalized:
                raise TrackingConflict("Completed targets are immutable")
        if normalized and sum((decimal(t["percent"]) for t in normalized), Decimal(0)) != 100:
            raise ValueError("Target percentages must sum to 100")
        state.update(
            targets=normalized,
            revision=1 if reset else old_revision + 1,
            armed_at=now_utc(),
        )
        return self._save(
            conn, state,
            "PLAN_RESET" if reset else "PLAN_SAVED",
            event_id,
            reset_index=reset_count + 1 if reset else 0,
        )

    def edit(self, trade_id, plan, *, expected_revision):
        self._verified()
        conn = self.driver.get_connection()
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("BEGIN IMMEDIATE")
            trade = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
            if trade is None:
                raise LookupError("Trade not found")
            state = self.edit_in_transaction(conn, dict(trade), plan, expected_revision)
            conn.commit()
            return state
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def eligible(state, observation, now=None):
        try:
            age = ((now or datetime.now(timezone.utc)) - timestamp(observation["observed_at"])).total_seconds()
            return (observation["status"] == "LIVE" and observation.get("timestamp_basis") == "PROVIDER_EVENT"
                    and observation["source_id"] == state["source_id"]
                    and observation["source_symbol"] == state["source_symbol"]
                    and 0 <= age <= 60 and decimal(observation["price"]) > 0
                    and timestamp(observation["observed_at"]) > timestamp(state["armed_at"]))
        except (ValueError, KeyError, TypeError, InvalidOperation):
            return False

    def observe(self, trade_id, observation, *, manual=False, expected_revision=None):
        self._verified()
        conn = self.driver.get_connection()
        try:
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("BEGIN IMMEDIATE")
            state, event_id, _ = self._load(conn, trade_id)
            if state is None:
                raise LookupError("Tracking not found")
            if manual and state["revision"] != expected_revision:
                raise TrackingConflict("Tracking plan changed; reload")
            trade = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
            if not trade or trade["status"] != "OPEN" or decimal(state["remaining_qty"], positive=False) == 0:
                return state
            if not self._unit_verified(trade):
                # No monetary close evidence without an explicit declaration.
                # A manual close reports the boundary; the automatic monitor
                # simply keeps waiting instead of backing off forever.
                if manual:
                    raise TrackingUnsupported(
                        "Local tracking needs an explicit unit declaration "
                        "(a USD position value or qty_unit=BASE); neither is recorded for this symbol."
                    )
                return state
            if (trade["symbol"] != state["symbol"] or trade["side"] != state["side"]
                or decimal(trade["entry_price"]) != decimal(state["entry_price"])
                or decimal(trade["qty"]) != decimal(state["initial_qty"])):
                raise TrackingConflict("External trade was corrected; tracking paused")
            if not manual and (not state["enabled"] or not self.eligible(state, observation)):
                return state
            if state["closures"] and not manual and timestamp(observation["observed_at"]) <= timestamp(state["closures"][-1]["observed_at"]):
                return state
            with localcontext() as ctx:
                ctx.prec = 60
                price = decimal(observation["price"])
                remaining = decimal(state["remaining_qty"])
                initial = decimal(state["initial_qty"])
                entry = decimal(state["entry_price"])
                direction = Decimal(1) if state["side"] in {"BUY", "LONG"} else Decimal(-1)
                closed_ids = {c["target_id"] for c in state["closures"]}
                hit = []
                stop = state["stop_loss"]
                if manual or (stop is not None and direction * (price - decimal(stop)) <= 0):
                    hit = [("MANUAL" if manual else "SL", remaining, stop)]
                else:
                    pending = [t for t in state["targets"] if t["id"] not in closed_ids]
                    for target in pending:
                        if direction * (price - decimal(target["price"])) >= 0:
                            amount = remaining if target == pending[-1] else initial * decimal(target["percent"]) / 100
                            amount = min(amount, remaining)
                            hit.append((target["id"], amount, target["price"]))
                            remaining -= amount
                    remaining = decimal(state["remaining_qty"])
                if not hit:
                    return state
                unit_usd = str(state.get("qty_unit") or "BASE").upper() == "USD"
                if unit_usd and entry == 0:
                    return state
                for target_id, amount, target_price in hit:
                    move = price - entry
                    pnl = (move / entry * amount if unit_usd else move * amount) * direction
                    state["closures"].append({"target_id": target_id, "qty": number(amount),
                        "price": number(price), "target_price": target_price, "gross_pnl": number(pnl),
                        "observed_at": now_utc() if manual else observation["observed_at"],
                        "plan_revision": state["revision"], "basis": "LOCAL_ESTIMATE"})
                    remaining -= amount
                    state["gross_pnl"] = number(decimal(state["gross_pnl"], positive=False) + pnl)
                state["remaining_qty"] = number(remaining)
                state["revision"] += 1
                result = self._save(conn, state, "LOCAL_CLOSE", event_id, observation)
                conn.commit()
                return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
