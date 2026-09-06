"""FIX wire-format helper with no configured transport or venue authority.

Encoding and decoding are local utilities. This module must not imply a certified FIX
session, broker acknowledgement, fill, or latency measurement.
"""

import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from app.services.execution.risk_interceptor import risk_interceptor

SOH = chr(1) # Standard FIX Field Delimiter (\x01)

class QuickFixDmaClient:
    """Local FIX encoder/decoder facade; it has no Direct Market Access transport."""

    def __init__(
        self,
        sender_comp_id: str = "KUANTRA_DMA_01",
        target_comp_id: str = "CME_GLOBEX",
        begin_string: str = "FIX.4.4"
    ):
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id
        self.begin_string = begin_string
        self.out_seq_num = 1
        self.in_seq_num = 1
        self.is_logged_on = False
        self.round_trip_latency_us: Optional[float] = None
        self.transport_connected = False

    @staticmethod
    def calculate_checksum(raw_payload: str) -> str:
        """Calculates standard 3-digit modulo 256 FIX checksum."""
        total_sum = sum(ord(c) for c in raw_payload)
        return f"{total_sum % 256:03d}"

    def encode_fix_message(self, msg_type: str, fields: Dict[int, Any]) -> str:
        """Encodes dictionary of integer tags into standard SOH-delimited FIX 4.4 packet."""
        sending_time = datetime.now(timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
        
        # Standard Header tags (except 8 and 9)
        body_fields = [
            (35, msg_type),
            (49, self.sender_comp_id),
            (56, self.target_comp_id),
            (34, self.out_seq_num),
            (52, sending_time)
        ]

        # Add custom payload fields
        for tag, val in fields.items():
            body_fields.append((tag, str(val)))

        # Construct body string
        body_str = "".join(f"{t}={v}{SOH}" for t, v in body_fields)
        body_len = len(body_str)

        # Prepend BeginString and BodyLength
        prefix = f"8={self.begin_string}{SOH}9={body_len}{SOH}"
        full_pre_checksum = f"{prefix}{body_str}"

        # Append CheckSum (Tag 10)
        checksum = self.calculate_checksum(full_pre_checksum)
        full_fix_msg = f"{full_pre_checksum}10={checksum}{SOH}"

        self.out_seq_num += 1
        return full_fix_msg

    @staticmethod
    def decode_fix_message(raw_msg: str) -> Dict[int, str]:
        """Decodes SOH or pipe-delimited FIX string into tag -> value mapping."""
        delimiter = SOH if SOH in raw_msg else "|"
        parts = [p for p in raw_msg.split(delimiter) if p]
        result: Dict[int, str] = {}
        for item in parts:
            if "=" in item:
                tag_str, val = item.split("=", 1)
                try:
                    result[int(tag_str)] = val
                except ValueError:
                    pass
        return result

    def send_new_order_single(
        self,
        symbol: str,
        side: str, # "BUY" | "SELL"
        qty: float,
        price: float,
        cl_ord_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fail closed at the transport boundary until a real FIX session exists.

        A local serializer cannot produce an order-level risk decision or venue
        acknowledgement.  Returning the unavailable state before evaluating the
        shared risk interceptor also keeps this experimental surface deterministic
        when the rest of the terminal has unrelated account state.
        """
        ord_id = cl_ord_id or f"FIX-{int(time.time() * 1000)}"

        if not self.transport_connected or not self.is_logged_on:
            return {
                "status": "EXPERIMENTAL_DISABLED",
                "cl_ord_id": ord_id,
                "symbol": symbol.upper(),
                "side": side.upper(),
                "requested_qty": qty,
                "requested_price": price,
                "execution_status": "NOT_SUBMITTED",
                "transport_connected": self.transport_connected,
                "round_trip_latency_us": None,
                "provenance": "FIX_SERIALIZATION_ONLY",
                "caveat": "No certified FIX transport or logged-on venue session is configured; no order was sent.",
                "timestamp": time.time()
            }

        approved, reason, risk_metadata = risk_interceptor.evaluate_order({
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "exchange": "CME_FIX_DMA",
        })
        if not approved:
            return {
                "status": "REJECTED_RISK_GUARDRAIL",
                "cl_ord_id": ord_id,
                "reason": reason,
                "risk_metadata": risk_metadata,
                "execution_status": "NOT_SUBMITTED",
                "transport_connected": False,
                "round_trip_latency_us": None,
                "provenance": "DETERMINISTIC_RISK_GATE",
                "caveat": "The order was rejected before the unavailable FIX transport boundary.",
                "timestamp": time.time(),
            }

        return {
            "status": "EXPERIMENTAL_DISABLED",
            "cl_ord_id": ord_id,
            "symbol": symbol.upper(),
            "side": side.upper(),
            "requested_qty": qty,
            "requested_price": price,
            "execution_status": "NOT_SUBMITTED",
            "transport_connected": False,
            "round_trip_latency_us": None,
            "provenance": "FIX_SERIALIZATION_ONLY",
            "caveat": "No certified FIX transport, session recovery, or broker connection is configured; no order was sent.",
            "risk_metadata": risk_metadata,
            "timestamp": time.time()
        }

    def send_cancel_replace(
        self,
        orig_cl_ord_id: str,
        new_qty: float,
        new_price: float,
        symbol: str = "ESM6"
    ) -> Dict[str, Any]:
        """Fail closed: a local encoder cannot cancel or replace a venue order."""
        new_cl_ord_id = f"FIX-REP-{int(time.time() * 1000)}"
        return {
            "status": "EXPERIMENTAL_DISABLED",
            "orig_cl_ord_id": orig_cl_ord_id,
            "new_cl_ord_id": new_cl_ord_id,
            "new_qty": new_qty,
            "new_price": new_price,
            "execution_status": "NOT_SUBMITTED",
            "transport_connected": False,
            "provenance": "FIX_SERIALIZATION_ONLY",
            "caveat": "No certified FIX transport is configured; no cancel/replace request was sent.",
            "timestamp": time.time()
        }

    def get_session_status(self) -> Dict[str, Any]:
        """Return the availability of this local wire-format helper truthfully."""
        return {
            "status": "EXPERIMENTAL_DISABLED",
            "provenance": "FIX_SERIALIZATION_ONLY",
            "caveat": "FIX encoding/decoding is available locally, but no broker transport or logged-on venue session exists.",
            "begin_string": self.begin_string,
            "sender_comp_id": self.sender_comp_id,
            "target_comp_id": self.target_comp_id,
            "is_logged_on": self.is_logged_on,
            "transport_connected": self.transport_connected,
            "outbound_seq_num": self.out_seq_num,
            "inbound_seq_num": self.in_seq_num,
            "round_trip_latency_us": self.round_trip_latency_us,
            "heartbeat_interval_sec": None,
            "supported_venues": []
        }

quickfix_dma_client = QuickFixDmaClient()
