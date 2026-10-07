from __future__ import annotations

from app.providers.calendar.base import CalendarProvider
from app.providers.calendar.bea import BeaCalendarProvider
from app.providers.calendar.bls import BlsCalendarProvider
from app.providers.calendar.cbn import CbnCalendarProvider
from app.providers.calendar.eia import EiaCalendarProvider
from app.providers.calendar.fed import FedCalendarProvider
from app.providers.calendar.holidays import HolidaysCalendarProvider
from app.providers.calendar.nbs import NbsCalendarProvider
from app.providers.calendar.opec import OpecCalendarProvider


def get_calendar_providers() -> list[CalendarProvider]:
    """Returns the registered phase-one official calendar providers."""
    return [
        FedCalendarProvider(),
        BlsCalendarProvider(),
        BeaCalendarProvider(),
        EiaCalendarProvider(),
        CbnCalendarProvider(),
        NbsCalendarProvider(),
        OpecCalendarProvider(),
        HolidaysCalendarProvider(),
    ]


__all__ = [
    "BeaCalendarProvider",
    "BlsCalendarProvider",
    "CalendarProvider",
    "CbnCalendarProvider",
    "EiaCalendarProvider",
    "FedCalendarProvider",
    "HolidaysCalendarProvider",
    "NbsCalendarProvider",
    "OpecCalendarProvider",
    "get_calendar_providers",
]
