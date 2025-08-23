from __future__ import annotations

from datetime import datetime, timezone, timedelta
import re
from typing import Dict, Tuple

# Regular expressions for validation
SBP_ID_RE = re.compile(
    r"^(?P<prefix>[A-Z])(?P<year>\d)(?P<doy>\d{3})(?P<hh>\d{2})(?P<mm>\d{2})(?P<ss>\d{2})"
    r"(?P<node>\d{4})(?P<ltr>[A-Z])(?P<seq5>\d{5})(?P<code4>\d{4})(?P<tail7>\d{7})$"
)

OP_NUMBER_RE = re.compile(
    r"^C(?P<pp>\d{2})(?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{2})(?P<serial>\d{7})$"
)

# Internal counters
_SBP_COUNTER: Dict[Tuple[datetime, str, str], int] = {}
_OP_COUNTER: Dict[Tuple[str, str], int] = {}

_MSK_TZ = timezone(timedelta(hours=3))


def _ensure_aware(dt: datetime) -> datetime:
    """Interpret naive datetimes as MSK (UTC+3)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_MSK_TZ)
    return dt


def generate_sbp_id(
    when: datetime,
    prefix: str = "B",
    node: str = "7310",
    route: str = "K",
    code4: str = "2001",
    tail7: str = "1571101",
) -> str:
    """Generate 32-character SBP identifier."""
    dt_utc = _ensure_aware(when).astimezone(timezone.utc)
    year = dt_utc.year % 10
    doy = f"{dt_utc.timetuple().tm_yday:03d}"
    hhmmss = dt_utc.strftime("%H%M%S")

    key = (dt_utc.replace(microsecond=0), node, route)
    seq = _SBP_COUNTER.get(key, 0) + 1
    _SBP_COUNTER[key] = seq
    seq5 = f"{seq:05d}"

    sbp_id = f"{prefix}{year}{doy}{hhmmss}{node}{route}{seq5}{code4}{tail7}"
    return sbp_id


def generate_op_number(when: datetime, pp: str = "42") -> str:
    """Generate 16-character bank operation number."""
    dt_msk = _ensure_aware(when).astimezone(_MSK_TZ)
    date_part = dt_msk.strftime("%d%m%y")

    key = (date_part, pp)
    serial = _OP_COUNTER.get(key, 0) + 1
    _OP_COUNTER[key] = serial
    serial7 = f"{serial:07d}"

    return f"C{pp}{date_part}{serial7}"


def validate_sbp_id(id32: str) -> None:
    if not SBP_ID_RE.fullmatch(id32):
        raise ValueError("Invalid SBP ID")


def validate_op_number(no16: str) -> None:
    if not OP_NUMBER_RE.fullmatch(no16):
        raise ValueError("Invalid operation number")

