"""Manual scheduler foundation. No cron is enabled by this module."""
from dataclasses import dataclass


@dataclass(frozen=True)
class MarketRadarSchedule:
    mode: str = "manual"
    future_modes: tuple[str, ...] = ("daily",)


def schedule() -> MarketRadarSchedule:
    return MarketRadarSchedule()
