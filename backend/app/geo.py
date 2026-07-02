import math
from datetime import datetime, timedelta, timezone

from .config import UTC_OFFSET_HOURS

EARTH_RADIUS_M = 6_371_000


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in meters."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def local_day_key(now: datetime | None = None) -> str:
    """Calendar date in East Africa Time, e.g. '2026-07-02'."""
    now = now or datetime.now(timezone.utc)
    return (now + timedelta(hours=UTC_OFFSET_HOURS)).strftime("%Y-%m-%d")


def previous_day_key(day_key: str) -> str:
    day = datetime.strptime(day_key, "%Y-%m-%d")
    return (day - timedelta(days=1)).strftime("%Y-%m-%d")
