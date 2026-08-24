"""Pydantic response models for the API (S2, issue #13/#14)."""

from pydantic import BaseModel


class Stop(BaseModel):
    stop_id: int
    name: str
    ars_number: str
    lat: float
    lon: float
    stop_type: str


class StopsResponse(BaseModel):
    stops: list[Stop]


class CongestionResponse(BaseModel):
    """Estimated wait and congestion grade for one stop at one hour."""

    stop_id: int
    name: str
    hour: int
    estimated_wait: float
    grade: str


class TimelinePoint(BaseModel):
    hour: int
    estimated_wait: float
    grade: str


class TimelineResponse(BaseModel):
    stop_id: int
    name: str
    timeline: list[TimelinePoint]


class CorridorStopSnapshot(BaseModel):
    stop_id: int
    name: str
    estimated_wait: float
    grade: str


class CorridorResponse(BaseModel):
    hour: int
    stops: list[CorridorStopSnapshot]


class ArrivalInfo(BaseModel):
    """One route's next-arrival estimate at a stop (issue #48, Seoul TOPIS)."""

    route_name: str
    route_id: str
    direction: str
    arrival_message_1: str
    arrival_message_2: str
    congestion_1: str | None
    congestion_2: str | None


class ArrivalsResponse(BaseModel):
    """Real-time arrivals for every route serving one stop.

    Independent of the wait-population estimate: ``available=False`` means
    TOPIS couldn't be reached (timeout/error).
    """

    stop_id: int
    name: str
    available: bool
    message: str | None
    arrivals: list[ArrivalInfo]


class StopContextResponse(BaseModel):
    """Weather + day-type context for one stop on one date (issue #47).

    precipitation_type is a normalized display label (맑음/비/눈 등). is_forecast=True
    means the fields came from a short-range forecast rather than an observed
    reading; precipitation/snowfall are 0.0 on forecast rows.
    """

    stop_id: int
    name: str
    date: int
    day_type: str
    temperature: float
    precipitation: float
    humidity: float
    snowfall: float
    wind_speed: float
    precipitation_type: str
    is_forecast: bool
    congestion_note: str
