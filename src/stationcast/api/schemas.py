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


class CorridorResponse(BaseModel):
    hour: int
    stops: list[CorridorStopSnapshot]
