"""Local FIX tag/value and state-machine prototype.

This module can serialize and inspect FIX-shaped messages for tests and future adapter
work. It is not a broker transport, certified FIX gateway, or venue session and must
not be used as evidence of logon, acknowledgement, recovery, or execution.
"""

import time
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("fix_gateway")

class FIXMessage:
    """FIX Protocol Tag-Value Message Encoder & Decoder."""

    def __init__(self, begin_string: str = "FIX.4.4", msg_type: str = "A"):
        self.begin_string = begin_string
        self.msg_type = msg_type
        self.tags: Dict[int, str] = {}

    def set_tag(self, tag: int, value: Any):
        self.tags[int(tag)] = str(value)

    def get_tag(self, tag: int) -> Optional[str]:
        return self.tags.get(int(tag))

    def serialize(self, delimiter: str = "\x01") -> str:
        """
        Serializes FIX message with Header (8, 9, 35), Body tags, and CheckSum (10).
        """
        # Format body string
        body_parts = [f"35={self.msg_type}"]
        for tag, val in sorted(self.tags.items()):
            if tag not in (8, 9, 35, 10):
                body_parts.append(f"{tag}={val}")

        body_str = delimiter.join(body_parts) + delimiter
        body_len = len(body_str.encode("utf-8"))

        header_str = f"8={self.begin_string}{delimiter}9={body_len}{delimiter}"
        pre_checksum = header_str + body_str

        # Compute CheckSum (Tag 10): Modulo 256 sum of all characters prior to tag 10
        checksum_val = sum(pre_checksum.encode("latin-1")) % 256
        checksum_str = f"{checksum_val:03d}"

        return f"{pre_checksum}10={checksum_str}{delimiter}"

    @classmethod
    def parse(cls, raw_msg: str, delimiter: str = "\x01") -> "FIXMessage":
        """Parse raw tag-value text for local inspection; transport validation is absent."""
        # Auto-detect delimiter if pipe | is used
        if "\x01" not in raw_msg and "|" in raw_msg:
            delimiter = "|"

        tokens = [t for t in raw_msg.split(delimiter) if t]
        tags_dict: Dict[int, str] = {}

        for token in tokens:
            if "=" in token:
                k, v = token.split("=", 1)
                try:
                    tags_dict[int(k)] = v
                except ValueError:
                    continue

        begin_str = tags_dict.get(8, "FIX.4.4")
        msg_type = tags_dict.get(35, "0")

        msg = cls(begin_string=begin_str, msg_type=msg_type)
        for t, v in tags_dict.items():
            msg.set_tag(t, v)

        return msg


class FIXSessionStateMachine:
    """Local protocol state model; it does not connect to or authenticate a venue."""

    def __init__(self, sender_comp_id: str = "KUANTRA_DMA", target_comp_id: str = "CME_DMA_GATEWAY", begin_string: str = "FIX.4.4"):
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id
        self.begin_string = begin_string
        self.state = "DISCONNECTED" # DISCONNECTED, CONNECTING, LOGON_SENT, ACTIVE, RECOVERY, LOGOUT_SENT
        self.out_seq_num = 1
        self.in_seq_num = 1
        self.heartbeat_interval = 30
        self.last_heartbeat_time = time.time()
        self.message_history: List[Dict[str, Any]] = []

    def _apply_header(self, msg: FIXMessage):
        msg.set_tag(49, self.sender_comp_id)
        msg.set_tag(56, self.target_comp_id)
        msg.set_tag(34, self.out_seq_num)
        msg.set_tag(52, time.strftime("%Y%m%d-%H:%M:%S.000", time.gmtime()))
        self.out_seq_num += 1

    def create_logon(self) -> str:
        """Generates 35=A Logon message."""
        msg = FIXMessage(begin_string=self.begin_string, msg_type="A")
        msg.set_tag(98, "0") # EncryptMethod = None
        msg.set_tag(108, str(self.heartbeat_interval))
        self._apply_header(msg)
        self.state = "LOGON_SENT"

        raw = msg.serialize(delimiter="|")
        self._record_msg("OUT", "LOGON", raw)
        return raw

    def create_heartbeat(self, test_req_id: Optional[str] = None) -> str:
        """Generates 35=0 Heartbeat message."""
        msg = FIXMessage(begin_string=self.begin_string, msg_type="0")
        if test_req_id:
            msg.set_tag(112, test_req_id)
        self._apply_header(msg)

        raw = msg.serialize(delimiter="|")
        self._record_msg("OUT", "HEARTBEAT", raw)
        return raw

    def create_new_order_single(
        self,
        cl_ord_id: str,
        symbol: str,
        side: str, # "1" for BUY, "2" for SELL
        qty: float,
        price: float,
        ord_type: str = "2", # "1" Market, "2" Limit
        tif: str = "0" # "0" Day, "1" GTC, "3" IOC, "4" FOK
    ) -> str:
        """Generates 35=D NewOrderSingle message."""
        msg = FIXMessage(begin_string=self.begin_string, msg_type="D")
        msg.set_tag(11, cl_ord_id)
        msg.set_tag(55, symbol)
        msg.set_tag(54, "1" if side.upper() in ("BUY", "1") else "2")
        msg.set_tag(38, str(qty))
        msg.set_tag(40, ord_type)
        if ord_type == "2":
            msg.set_tag(44, str(price))
        msg.set_tag(59, tif)
        msg.set_tag(60, time.strftime("%Y%m%d-%H:%M:%S.000", time.gmtime()))

        self._apply_header(msg)
        raw = msg.serialize(delimiter="|")
        self._record_msg("OUT", "NEW_ORDER_SINGLE", raw)
        return raw

    def create_order_cancel_request(self, orig_cl_ord_id: str, cl_ord_id: str, symbol: str, side: str) -> str:
        """Generates 35=F OrderCancelRequest message."""
        msg = FIXMessage(begin_string=self.begin_string, msg_type="F")
        msg.set_tag(41, orig_cl_ord_id)
        msg.set_tag(11, cl_ord_id)
        msg.set_tag(55, symbol)
        msg.set_tag(54, "1" if side.upper() in ("BUY", "1") else "2")
        msg.set_tag(60, time.strftime("%Y%m%d-%H:%M:%S.000", time.gmtime()))

        self._apply_header(msg)
        raw = msg.serialize(delimiter="|")
        self._record_msg("OUT", "ORDER_CANCEL_REQUEST", raw)
        return raw

    def process_incoming(self, raw_msg: str) -> Dict[str, Any]:
        """Processes incoming FIX stream and updates session state."""
        msg = FIXMessage.parse(raw_msg)
        msg_type = msg.msg_type
        self.in_seq_num += 1
        self.last_heartbeat_time = time.time()

        if msg_type == "A": # Logon Confirmed
            self.state = "ACTIVE"
            self._record_msg("IN", "LOGON_CONFIRM", raw_msg)
            return {"status": "SESSION_ACTIVE", "msg_type": "LOGON_ACK"}

        elif msg_type == "0": # Heartbeat
            self._record_msg("IN", "HEARTBEAT", raw_msg)
            return {"status": "HEARTBEAT_ACK", "msg_type": "HEARTBEAT"}

        elif msg_type == "1": # Test Request -> Reply with Heartbeat
            test_req_id = msg.get_tag(112)
            reply = self.create_heartbeat(test_req_id=test_req_id)
            self._record_msg("IN", "TEST_REQUEST", raw_msg)
            return {"status": "TEST_REQUEST_REPLIED", "response_fix": reply}

        elif msg_type == "8": # Execution Report
            exec_id = msg.get_tag(17)
            cl_ord_id = msg.get_tag(11)
            ord_status = msg.get_tag(39) # 0=New, 1=Partial, 2=Filled, 4=Cancelled, 8=Rejected
            cum_qty = float(msg.get_tag(14) or 0.0)
            leaves_qty = float(msg.get_tag(151) or 0.0)
            avg_px = float(msg.get_tag(6) or 0.0)

            self._record_msg("IN", "EXECUTION_REPORT", raw_msg)
            return {
                "status": "EXECUTION_REPORT_PROCESSED",
                "exec_id": exec_id,
                "cl_ord_id": cl_ord_id,
                "ord_status": ord_status,
                "cum_qty": cum_qty,
                "leaves_qty": leaves_qty,
                "avg_px": avg_px
            }

        return {"status": "PROCESSED", "msg_type": msg_type}

    def _record_msg(self, direction: str, msg_name: str, raw_fix: str):
        self.message_history.append({
            "direction": direction,
            "msg_name": msg_name,
            "raw": raw_fix,
            "timestamp": time.time()
        })
        if len(self.message_history) > 100:
            self.message_history.pop(0)

# Global FIX Gateway instance
fix_session = FIXSessionStateMachine()
