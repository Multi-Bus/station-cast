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
    """Raw estimated wait for one stop at one hour.

    No grade (여유/보통/혼잡/매우혼잡) field yet
    """

    stop_id: int
    name: str
    hour: int
    estimated_wait: float


class TimelinePoint(BaseModel):
    hour: int
    estimated_wait: float


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
