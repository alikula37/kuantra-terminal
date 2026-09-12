"""Journal position identity; absent historical identity stays unknown."""


def normalize_position_type(value, side: str) -> str:
    position_type = str(value or "UNKNOWN").upper()
    allowed = {"SPOT": {"BUY"}, "LONG": {"BUY", "LONG"}, "SHORT": {"SELL", "SHORT"}}
    if position_type != "UNKNOWN" and (
        position_type not in allowed or str(side).upper() not in allowed[position_type]
    ):
        raise ValueError("Position type contradicts trade direction or is unsupported")
    return position_type
