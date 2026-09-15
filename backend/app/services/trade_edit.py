"""Revisioned journal trade correction.

Corrections never rewrite history: the compatibility row is updated and a new
``TradeCorrected`` event captures the full snapshot plus the explicit previous
values in its provenance.  When a local TP/SL plan exists it is the authority
for stops and targets: a journal stop/take-profit edit updates the plan and the
legacy columns in the same transaction, quantity/entry corrections reset the
plan only while it has no close evidence, and after a partial close the size
fields are locked so the close evidence cannot silently change.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.position_math import instrument_unit_basis
from app.core.trade_rules import (
    TradeRuleError,
    normalize_leverage,
    validate_notes,
    validate_stop_and_targets,
)
from app.core.trade_time import TradeTimeError, parse_user_time, validate_not_future, to_utc_iso
from app.db.repositories.evidence_ledger_repo import EvidenceLedgerRepository
from app.db.sqlite_driver import SQLiteRevisionConflict, sqlite_driver
from app.db.sync_pipeline import sync_pipeline
from app.services.local_tracking import TrackingConflict

_OPEN_EDITABLE = frozenset(
    {"entry_price", "entry_time", "qty", "leverage", "stop_loss", "take_profit", "notes", "qty_unit"}
)
_CLOSED_EDITABLE = frozenset({"notes", "qty_unit", "exit_price", "exit_time"})
_CANCELED_EDITABLE: frozenset[str] = frozenset()


class TradeEditError(ValueError):
    def __init__(
        self,
        reason: str,
        message: str,
        *,
        field: Optional[str] = None,
        status_code: int = 422,
    ):
        super().__init__(message)
        self.reason = reason
        self.field = field
        self.status_code = status_code


class TradeEditConflict(TradeEditError):
    def __init__(self, reason: str, message: str, *, field: Optional[str] = None):
        super().__init__(reason, message, field=field, status_code=409)


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


class TradeEditService:
    def __init__(self, driver=None, catalog=None):
        self.driver = driver or sqlite_driver
        if catalog is None:
            from app.services.market_data.instrument_catalog import InstrumentCatalog

            catalog = InstrumentCatalog(db_path=self.driver.db_path)
        self.catalog = catalog

    def _catalog_verified(self, symbol) -> bool:
        try:
            return bool(self.catalog.is_verified(str(symbol or "")))
        except Exception:  # noqa: BLE001 - verification must never block an edit
            return False

    # -- read helpers -----------------------------------------------------

    def _tracking_state(self, trade_id: str) -> Optional[Dict[str, Any]]:
        with self.driver.get_connection() as conn:
            row = conn.execute(
                "SELECT normalized_payload_json FROM evidence_events "
                "WHERE correlation_id=? AND account_id='local-journal' AND venue='local-journal' "
                "AND event_type='PositionProjectionUpdated' "
                "ORDER BY chain_date_utc DESC, chain_sequence DESC LIMIT 1",
                (trade_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row["normalized_payload_json"])
        except (TypeError, json.JSONDecodeError):
            return None
        state = payload.get("local_tracking") if isinstance(payload, dict) else None
        return state if isinstance(state, dict) else None

    @staticmethod
    def _plan_payload(state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "enabled": bool(state.get("enabled", True)),
            "source_id": state.get("source_id"),
            "source_symbol": state.get("source_symbol"),
            "stop_loss": _number(state.get("stop_loss")),
            "targets": [
                {"price": _number(target.get("price")), "percent": _number(target.get("percent"))}
                for target in state.get("targets", [])
            ],
        }

    def revision_history(self, trade_id: str) -> list[Dict[str, Any]]:
        ledger = EvidenceLedgerRepository(self.driver.db_path)
        events = ledger.list_events_for_trade(
            trade_id,
            account_id="local-journal",
            venues=("local-journal", "legacy"),
        )
        history = []
        for event in events:
            provenance = event.get("provenance") or {}
            correction = provenance.get("correction") if isinstance(provenance, dict) else None
            if not isinstance(correction, dict):
                continue
            try:
                revision = int(correction.get("expected_revision", 0)) + 1
            except (TypeError, ValueError):
                revision = None
            history.append(
                {
                    "event_id": event.get("event_id"),
                    "occurred_at_utc": event.get("occurred_at_utc"),
                    "revision": revision,
                    "changed_fields": correction.get("fields") or {},
                    "edit_source": str(correction.get("edit_source") or "UNKNOWN"),
                }
            )
        return history

    # -- plan synchronization --------------------------------------------

    @staticmethod
    def _target_closed(targets: list, closures: list, target_id: str) -> bool:
        return any(closure.get("target_id") == target_id for closure in closures)

    def _synchronize_plan(
        self,
        *,
        tracking: Optional[Dict[str, Any]],
        plan_changes: Optional[Dict[str, Any]],
        stop_changed: bool,
        target_changed: bool,
        new_stop: Any,
        new_target: Any,
        size_changed: bool,
        reset: bool,
    ) -> tuple[Optional[Dict[str, Any]], bool, Optional[int]]:
        """Return ``(plan_payload, reset, expected_plan_revision)``.

        ``None`` payload means no plan write is required.  Multi-target plans
        reject a single take-profit edit instead of silently rewriting the
        ladder; single pending targets accept it.
        """

        if plan_changes is not None:
            payload = {
                "enabled": bool(plan_changes.get("enabled", True)),
                "source_id": plan_changes.get("source_id"),
                "source_symbol": plan_changes.get("source_symbol"),
                "stop_loss": _number(plan_changes.get("stop_loss")),
                "targets": [
                    {"price": _number(target.get("price")), "percent": _number(target.get("percent"))}
                    for target in plan_changes.get("targets", [])
                ],
            }
            expected = int(plan_changes.get("expected_revision", 0))
            return payload, bool(reset), expected

        if tracking is None:
            return None, False, None

        if not (size_changed or stop_changed or target_changed):
            return None, False, None

        payload = self._plan_payload(tracking)
        if stop_changed:
            payload["stop_loss"] = _number(new_stop)
        if target_changed:
            targets = payload.get("targets") or []
            closures = tracking.get("closures") or []
            if len(targets) != 1 or self._target_closed(targets, closures, "TP1"):
                raise TradeEditError(
                    "TARGETS_MANAGED_BY_PLAN",
                    "The local tracking plan has multiple or completed targets; "
                    "edit the plan targets instead of the single take-profit field.",
                    field="take_profit",
                )
            payload["targets"] = [{"price": _number(new_target), "percent": _number(targets[0].get("percent"))}]
        expected = None if reset else int(tracking.get("revision") or 1)
        return payload, bool(reset), expected

    def _plan_differs(self, tracking: Optional[Dict[str, Any]], plan: Dict[str, Any]) -> bool:
        """Compare the whole plan payload against the stored plan state."""

        if tracking is None:
            return True
        if bool(plan.get("enabled", True)) != bool(tracking.get("enabled")):
            return True
        if (plan.get("source_id"), plan.get("source_symbol")) != (
            tracking.get("source_id"),
            tracking.get("source_symbol"),
        ):
            return True
        if _number(plan.get("stop_loss")) != _number(tracking.get("stop_loss")):
            return True
        if int(plan.get("expected_revision", 0)) != int(tracking.get("revision") or 0):
            # A stale plan revision is a conflict; treat it as dirty so the
            # transactional revision check runs instead of a false no_change.
            return True
        try:
            new_targets = [
                (float(target["price"]), float(target["percent"]))
                for target in plan.get("targets") or []
            ]
            old_targets = [
                (float(target["price"]), float(target["percent"]))
                for target in tracking.get("targets") or []
            ]
        except (KeyError, TypeError, ValueError):
            return True
        return new_targets != old_targets

    @staticmethod
    def _close_result(
        *,
        side: str,
        entry_price: Optional[float],
        exit_price: float,
        qty_value: Optional[float],
        commission_value: float,
        stop_value: Optional[float],
        unit_ready: bool,
    ) -> tuple[Optional[float], Optional[float]]:
        """Return the user-reported gross P/L and R only for a verified unit."""

        if not unit_ready or qty_value is None or entry_price is None:
            return None, None
        direction = 1.0 if side in ("BUY", "LONG") else -1.0
        gross = direction * (exit_price - entry_price) * qty_value - commission_value
        r_multiple = None
        if stop_value:
            risk_unit = (
                (entry_price - stop_value) if side in ("BUY", "LONG") and entry_price > stop_value
                else (stop_value - entry_price) if side not in ("BUY", "LONG") and stop_value > entry_price
                else None
            )
            if risk_unit and qty_value > 0:
                r_multiple = round(gross / (risk_unit * qty_value), 2)
        return round(gross, 2), r_multiple

    # -- write ------------------------------------------------------------

    def edit(
        self,
        trade_id: str,
        changes: Dict[str, Any],
        *,
        expected_revision: int,
        tracking_plan: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        existing = self.driver.get_trade(trade_id)
        if existing is None:
            raise TradeEditError("TRADE_NOT_FOUND", "Trade not found.", status_code=404)
        status = str(existing.get("status") or "OPEN").upper()
        current_revision = int(existing.get("revision") or 1)
        if expected_revision is None or int(expected_revision) != current_revision:
            raise TradeEditConflict(
                "REVISION_CONFLICT",
                "The trade changed since this editor was opened; reload before saving.",
            )

        requested_status = str(changes.get("status") or status).upper()
        if requested_status not in {"OPEN", "CLOSED", "CANCELED"}:
            raise TradeEditError(
                "TRADE_STATUS_INVALID",
                "Trade status must be OPEN, CLOSED or CANCELED.",
                field="status",
            )
        status_change = requested_status != status
        requested = {key: value for key, value in changes.items() if key in _OPEN_EDITABLE}
        if "exit_price" in changes or "exit_time" in changes:
            if not ((status_change and requested_status == "CLOSED") or (status == "CLOSED" and not status_change)):
                raise TradeEditError(
                    "EXIT_FIELDS_REQUIRE_CLOSE",
                    "Exit price and time can only be set for a completed trade.",
                    field="exit_price" if "exit_price" in changes else "exit_time",
                )
        if status == "CLOSED" and not status_change:
            forbidden = sorted(set(requested) - _CLOSED_EDITABLE)
            if forbidden:
                raise TradeEditError(
                    "TRADE_CLOSED_NOTES_ONLY",
                    "A completed trade only allows note corrections; reopen it to change other fields.",
                    field=forbidden[0],
                )
        if status == "CLOSED" and requested_status == "CANCELED":
            forbidden = sorted(set(requested) - {"notes"})
            if forbidden:
                raise TradeEditError(
                    "TRADE_CLOSED_NOTES_ONLY",
                    "Canceling a completed trade only allows the status and notes change.",
                    field=forbidden[0],
                )

        if tracking_plan is not None and ({"stop_loss", "take_profit"} & set(requested)):
            raise TradeEditError(
                "AMBIGUOUS_ORDER_EDIT",
                "Edit either the tracking plan or the single stop/target, not both.",
                field="stop_loss",
            )

        reference_time = now or datetime.now(timezone.utc)
        tracking = self._tracking_state(trade_id) if requested_status == "OPEN" else None
        has_closures = bool(tracking and tracking.get("closures"))

        payload: Dict[str, Any] = {"id": trade_id, "revision": current_revision + 1}
        changed: Dict[str, Dict[str, Any]] = {}

        def apply(field: str, old_value: Any, new_value: Any) -> None:
            if old_value == new_value:
                return
            payload[field] = new_value
            changed[field] = {"from": old_value, "to": new_value}

        if status_change:
            apply("status", status, requested_status)
            if requested_status == "OPEN":
                # Reopening clears the recorded close result; the append-only
                # ledger keeps the previous values in the correction provenance.
                if existing.get("exit_price") is not None:
                    apply("exit_price", _number(existing.get("exit_price")), None)
                if existing.get("exit_time") is not None:
                    apply("exit_time", str(existing.get("exit_time")), None)
                if _number(existing.get("pnl")) not in (None, 0.0):
                    apply("pnl", _number(existing.get("pnl")), 0.0)
                if existing.get("r_multiple") is not None:
                    apply("r_multiple", _number(existing.get("r_multiple")), None)
                if existing.get("close_source"):
                    apply("close_source", str(existing.get("close_source")), None)
            elif requested_status == "CLOSED":
                # Closing from the editor records a user-reported exit.
                exit_price_value = (
                    _number(changes.get("exit_price"))
                    if "exit_price" in changes
                    else _number(existing.get("exit_price"))
                )
                exit_time_raw = changes.get("exit_time") if "exit_time" in changes else existing.get("exit_time")
                if exit_price_value is None or exit_price_value <= 0:
                    raise TradeRuleError(
                        "EXIT_REQUIRED_FOR_CLOSED",
                        "Closing a trade requires the realized exit price and time.",
                        field="exit_price",
                    )
                if not exit_time_raw:
                    raise TradeRuleError(
                        "EXIT_REQUIRED_FOR_CLOSED",
                        "Closing a trade requires the realized exit price and time.",
                        field="exit_time",
                    )
                parsed_exit = parse_user_time(str(exit_time_raw), field="exit_time", now=reference_time)
                validate_not_future(parsed_exit, field="exit_time", now=reference_time)
                parsed_entry = parse_user_time(str(existing.get("entry_time")), now=reference_time)
                if parsed_exit < parsed_entry:
                    raise TradeRuleError(
                        "EXIT_BEFORE_ENTRY",
                        "The exit cannot be earlier than the entry.",
                        field="exit_time",
                    )
                side = str(existing.get("side") or "BUY")
                qty_value = _number(payload.get("qty", existing.get("qty")))
                entry_value = _number(payload.get("entry_price", existing.get("entry_price")))
                unit_ready = instrument_unit_basis(
                    existing.get("symbol"),
                    qty_unit=payload.get("qty_unit", existing.get("qty_unit")),
                    server_verified=self._catalog_verified(existing.get("symbol")),
                )["contract_size"] == "BASE_UNIT"
                gross, r_multiple_value = self._close_result(
                    side=side,
                    entry_price=entry_value,
                    exit_price=exit_price_value,
                    qty_value=qty_value,
                    commission_value=_number(existing.get("commission")) or 0.0,
                    stop_value=_number(payload.get("stop_loss", existing.get("stop_loss"))),
                    unit_ready=unit_ready,
                )
                apply("exit_price", _number(existing.get("exit_price")), exit_price_value)
                apply("exit_time", existing.get("exit_time"), to_utc_iso(parsed_exit))
                apply("pnl", _number(existing.get("pnl")), gross)
                apply("r_multiple", _number(existing.get("r_multiple")), r_multiple_value)
                apply("close_source", existing.get("close_source"), "USER_REPORTED")

        if "entry_price" in requested:
            new_entry = _number(requested["entry_price"])
            if new_entry is None or new_entry <= 0:
                raise TradeRuleError("ENTRY_INVALID", "Entry price must be a positive number.", field="entry_price")
            apply("entry_price", _number(existing.get("entry_price")), new_entry)

        if "qty" in requested:
            new_qty = _number(requested["qty"])
            if new_qty is None or new_qty <= 0:
                raise TradeRuleError("QTY_INVALID", "Quantity must be a positive number.", field="qty")
            apply("qty", _number(existing.get("qty")), new_qty)

        if "leverage" in requested:
            declared = normalize_leverage(requested["leverage"], existing.get("position_type"))
            apply("leverage", _number(existing.get("leverage")), declared)

        if "qty_unit" in requested:
            unit = str(requested["qty_unit"] or "UNKNOWN").upper()
            if unit not in {"BASE", "UNKNOWN"}:
                raise TradeRuleError("QTY_UNIT_INVALID", "Quantity unit must be BASE or UNKNOWN.", field="qty_unit")
            apply("qty_unit", str(existing.get("qty_unit") or "UNKNOWN").upper(), unit)

        effective_entry = payload.get("entry_price", _number(existing.get("entry_price")))
        effective_side = str(existing.get("side") or "BUY")
        stop_present = "stop_loss" in requested
        target_present = "take_profit" in requested
        has_active_plan = tracking is not None or tracking_plan is not None
        # The legacy take-profit column mirrors the plan's first target; it is a
        # derived value while a plan exists, so an entry correction is validated
        # against the plan itself instead of the mirrored column.
        if stop_present or target_present or ("entry_price" in changed and not has_active_plan):
            stop_value, target_value = validate_stop_and_targets(
                entry_price=float(effective_entry),
                side=effective_side,
                stop_loss=requested.get("stop_loss", existing.get("stop_loss")),
                take_profit=requested.get("take_profit", existing.get("take_profit")),
            )
            if stop_present or "entry_price" in changed:
                apply("stop_loss", _number(existing.get("stop_loss")), stop_value)
            if target_present or "entry_price" in changed:
                apply("take_profit", _number(existing.get("take_profit")), target_value)

        if "entry_time" in requested:
            parsed = parse_user_time(str(requested["entry_time"]), field="entry_time", now=reference_time)
            validate_not_future(parsed, field="entry_time", now=reference_time)
            exit_time = existing.get("exit_time")
            if exit_time:
                parsed_exit = parse_user_time(str(exit_time), field="exit_time", now=reference_time)
                if parsed > parsed_exit:
                    raise TradeRuleError(
                        "ENTRY_AFTER_EXIT",
                        "The entry time cannot be later than the exit time.",
                        field="entry_time",
                    )
            normalized_new = to_utc_iso(parsed)
            normalized_old = to_utc_iso(parse_user_time(str(existing.get("entry_time")), now=reference_time))
            apply("entry_time", normalized_old, normalized_new)
            if "entry_time" in changed:
                payload["entry_time_source"] = "USER"

        if "notes" in requested:
            notes = validate_notes(requested["notes"])
            apply("notes", str(existing.get("notes") or ""), notes)

        correction_requested = (
            ("exit_price" in changes)
            or ("exit_time" in changes)
            or ("qty_unit" in changes and "qty_unit" in changed)
        )
        if status == "CLOSED" and not status_change and correction_requested:
            # Correcting a completed trade's unit or exit data recomputes the
            # user-reported result; the previous values stay in provenance.
            exit_price_value = (
                _number(changes.get("exit_price"))
                if "exit_price" in changes
                else _number(existing.get("exit_price"))
            )
            exit_time_raw = changes.get("exit_time") if "exit_time" in changes else existing.get("exit_time")
            if exit_price_value is None or exit_price_value <= 0:
                raise TradeRuleError(
                    "EXIT_REQUIRED_FOR_CLOSED",
                    "A completed trade needs a positive exit price and time.",
                    field="exit_price",
                )
            if not exit_time_raw:
                raise TradeRuleError(
                    "EXIT_REQUIRED_FOR_CLOSED",
                    "A completed trade needs a positive exit price and time.",
                    field="exit_time",
                )
            parsed_exit = parse_user_time(str(exit_time_raw), field="exit_time", now=reference_time)
            validate_not_future(parsed_exit, field="exit_time", now=reference_time)
            parsed_entry = parse_user_time(str(existing.get("entry_time")), now=reference_time)
            if parsed_exit < parsed_entry:
                raise TradeRuleError(
                    "EXIT_BEFORE_ENTRY",
                    "The exit cannot be earlier than the entry.",
                    field="exit_time",
                )
            unit_ready = instrument_unit_basis(
                existing.get("symbol"),
                qty_unit=payload.get("qty_unit", existing.get("qty_unit")),
                server_verified=self._catalog_verified(existing.get("symbol")),
            )["contract_size"] == "BASE_UNIT"
            gross, r_multiple_value = self._close_result(
                side=str(existing.get("side") or "BUY"),
                entry_price=_number(existing.get("entry_price")),
                exit_price=exit_price_value,
                qty_value=_number(existing.get("qty")),
                commission_value=_number(existing.get("commission")) or 0.0,
                stop_value=_number(existing.get("stop_loss")),
                unit_ready=unit_ready,
            )
            apply("exit_price", _number(existing.get("exit_price")), exit_price_value)
            apply("exit_time", existing.get("exit_time"), to_utc_iso(parsed_exit))
            apply("pnl", _number(existing.get("pnl")), gross)
            apply("r_multiple", _number(existing.get("r_multiple")), r_multiple_value)
            if existing.get("close_source") is None:
                payload["close_source"] = "USER_REPORTED"

        plan_dirty = False
        if tracking_plan is not None and requested_status == "OPEN":
            plan_stop = _number(tracking_plan.get("stop_loss"))
            plan_targets = tracking_plan.get("targets") or []
            apply("stop_loss", _number(existing.get("stop_loss")), plan_stop)
            first_target = _number(plan_targets[0].get("price")) if plan_targets else None
            apply("take_profit", _number(existing.get("take_profit")), first_target)
            plan_dirty = self._plan_differs(tracking, tracking_plan)

        if not changed and not plan_dirty:
            return {
                "trade": existing,
                "changed_fields": {},
                "revision": current_revision,
                "no_change": True,
                "tracking": tracking,
            }

        if plan_dirty and not changed:
            # Plan-only correction: record an explicit plan revision marker so
            # the revision history and provenance carry the change.
            previous_plan_revision = int(tracking.get("revision") or 0) if tracking else 0
            changed["tracking_plan"] = {
                "from": previous_plan_revision,
                "to": previous_plan_revision + 1 if tracking else 1,
            }

        size_changed = bool({"entry_price", "qty"} & set(changed))
        if tracking_plan is not None and plan_dirty:
            # Explicit plan edits never silently extend the plan lineage; a size
            # correction resets it (only valid before any close evidence).
            plan_payload, plan_reset, expected_plan_revision = self._synchronize_plan(
                tracking=tracking,
                plan_changes=tracking_plan,
                stop_changed=False,
                target_changed=False,
                new_stop=None,
                new_target=None,
                size_changed=size_changed,
                reset=size_changed,
            )
        elif tracking is not None and (size_changed or "stop_loss" in changed or "take_profit" in changed):
            if size_changed and has_closures:
                raise TradeEditError(
                    "TRACKING_PARTIAL_CLOSE_LOCKS_SIZE",
                    "Entry price and quantity are locked after a partial close; the close evidence is immutable.",
                    field="qty" if "qty" in changed else "entry_price",
                )
            plan_payload, plan_reset, expected_plan_revision = self._synchronize_plan(
                tracking=tracking,
                plan_changes=None,
                stop_changed="stop_loss" in changed,
                target_changed="take_profit" in changed,
                new_stop=payload.get("stop_loss"),
                new_target=payload.get("take_profit"),
                size_changed=size_changed,
                reset=size_changed,
            )
        else:
            plan_payload, plan_reset, expected_plan_revision = None, False, None

        if plan_reset and plan_payload is not None:
            self._ensure_plan_valid_after_resize(
                plan_payload,
                entry_price=float(effective_entry),
                side=effective_side,
            )

        provenance_extra = {
            "correction": {
                "fields": changed,
                "edit_source": "JOURNAL_EDIT",
                "expected_revision": current_revision,
            }
        }
        if plan_payload is not None:
            provenance_extra["correction"]["tracking_plan_updated"] = True
        try:
            updated = sync_pipeline.record_and_sync_trade(
                payload,
                source="journal_edit",
                source_ref="api",
                provenance_extra=provenance_extra,
                occurred_at=to_utc_iso(reference_time),
                local_tracking_plan=plan_payload,
                local_tracking_reset=plan_reset,
                local_tracking_expected_revision=expected_plan_revision,
                expected_revision=current_revision,
            )
        except SQLiteRevisionConflict as exc:
            raise TradeEditConflict("REVISION_CONFLICT", str(exc)) from exc
        except TrackingConflict as exc:
            raise TradeEditConflict("TRACKING_CONFLICT", str(exc)) from exc
        except LookupError as exc:
            raise TradeEditError("TRADE_NOT_FOUND", str(exc), status_code=404) from exc
        except TradeRuleError:
            raise
        except TradeTimeError:
            raise
        except ValueError as exc:
            if "verified base unit" in str(exc):
                raise TradeEditError("TRACKING_UNIT_UNVERIFIED", str(exc), status_code=422) from exc
            raise TradeEditError("EDIT_REJECTED", str(exc)) from exc
        return {
            "trade": updated,
            "changed_fields": changed,
            "revision": int(updated.get("revision") or current_revision + 1),
            "no_change": False,
            "tracking": self._tracking_state(trade_id) if requested_status == "OPEN" else None,
        }

    @staticmethod
    def _ensure_plan_valid_after_resize(plan: Dict[str, Any], *, entry_price: float, side: str) -> None:
        long = str(side or "").upper() in {"BUY", "LONG"}
        previous = entry_price
        for target in plan.get("targets", []):
            price = _number(target.get("price"))
            if price is None or (long and price <= previous) or (not long and price >= previous):
                raise TradeEditError(
                    "TRACKING_PLAN_INVALID_AFTER_EDIT",
                    "The corrected entry price invalidates the existing local TP plan; edit the plan first.",
                    field="entry_price",
                )
            previous = price
        stop = _number(plan.get("stop_loss"))
        if stop is not None and ((long and stop >= entry_price) or (not long and stop <= entry_price)):
            raise TradeEditError(
                "TRACKING_PLAN_INVALID_AFTER_EDIT",
                "The corrected entry price invalidates the existing local stop; edit the plan first.",
                field="entry_price",
            )


trade_edit_service = TradeEditService()
