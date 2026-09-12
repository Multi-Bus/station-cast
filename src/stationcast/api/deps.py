"""Lookups and clock helpers shared by the API routers.

Routers must reach the clock helpers through the module (``deps.current_hour()``)
rather than importing the names directly: tests monkeypatch them here, and a
direct ``from ... import current_hour`` binds a copy the patch never reaches.
"""

from datetime import datetime

import pandas as pd
from fastapi import HTTPException

from stationcast.api.data import CorridorData


def current_hour() -> int:
    return datetime.now().hour


def current_date() -> int:
    return int(datetime.now().strftime("%Y%m%d"))


def validate_date(date: int) -> None:
    """Reject a YYYYMMDD date that isn't a real calendar date (issue #137).

    ``date`` is a plain ``int`` query param, so FastAPI/Pydantic accepts any
    integer -- 0, negative, wrong-length, or a real-looking-but-invalid date
    like 20260230 (Feb 30) all parse fine as ints and used to blow up later
    as an unhandled ValueError (500) instead of a 422.
    """
    try:
        datetime.strptime(str(date), "%Y%m%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid date {date}") from exc


def stop_wait(data: CorridorData, stop_id: int) -> pd.DataFrame:
    wait = data.wait[data.wait["표준버스정류장ID"] == stop_id]
    if wait.empty:
        raise HTTPException(status_code=404, detail=f"stop {stop_id} not found")
    return wait


def stop_capacity(data: CorridorData, stop_id: int) -> float:
    row = data.capacity[data.capacity["표준버스정류장ID"] == stop_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"stop {stop_id} not found")
    return float(row["포용인원"].iloc[0])


def stop_name(data: CorridorData, stop_id: int) -> str:
    row = data.stops[data.stops["표준버스정류장ID"] == stop_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"stop {stop_id} not found")
    return str(row["정류장명"].iloc[0])


def stop_ars_number(data: CorridorData, stop_id: int) -> str:
    row = data.stops[data.stops["표준버스정류장ID"] == stop_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"stop {stop_id} not found")
    return str(row["ARS번호"].iloc[0])
