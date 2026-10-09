"""Simulated outside world: the demo clock and the remote unlock. Nothing here calls out."""
from __future__ import annotations

from datetime import datetime

# Fixed daytime clock so demos are repeatable. Override with TRIAGE_NOW.
DEFAULT_DEMO_NOW = datetime(2026, 10, 9, 12, 0)


def get_now(setting: str | None) -> datetime:
    """None or "" -> fixed demo noon. "real" -> system clock. Otherwise an ISO time."""
    if not setting:
        return DEFAULT_DEMO_NOW
    if setting.strip().lower() == "real":
        return datetime.now().replace(microsecond=0)
    try:
        return datetime.fromisoformat(setting.strip())
    except ValueError:
        raise ValueError(
            f"TRIAGE_NOW must be 'real' or an ISO time like 2026-10-09T23:30, got {setting!r}"
        ) from None


def clock_label(setting: str | None) -> str:
    return "system clock" if (setting or "").strip().lower() == "real" else "simulated clock"


def remote_unlock(vehicle_id: str, now: datetime) -> dict:
    """Pretend to send an unlock command. Always succeeds."""
    return {"ok": True, "vehicle_id": vehicle_id, "sent_at": now.isoformat(timespec="seconds"),
            "simulated": True}
