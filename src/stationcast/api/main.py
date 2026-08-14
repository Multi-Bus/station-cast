"""FastAPI application entrypoint.

/stops, /stops/{id}/congestion, /stops/{id}/timeline, /corridor added in
S2 (issue #13).
"""

from datetime import datetime

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query

from stationcast.api.data import CorridorData, get_corridor_data
from stationcast.api.schemas import (
    CongestionResponse,
    CorridorResponse,
    CorridorStopSnapshot,
    Stop,
    StopsResponse,
    TimelinePoint,
    TimelineResponse,
)
from stationcast.estimator.congestion import grade_wait

app = FastAPI(title="Station Cast API")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/stops", response_model=StopsResponse)
def list_stops(data: CorridorData = Depends(get_corridor_data)) -> StopsResponse:
    """List every stop in the corridor with display metadata."""
    stops = [
        Stop(
            stop_id=int(row["표준버스정류장ID"]),
            name=str(row["정류장명"]),
            ars_number=str(row["ARS번호"]),
            lat=float(row["Y좌표"]),
            lon=float(row["X좌표"]),
            stop_type=str(row["정류소 타입"]),
        )
        for _, row in data.stops.iterrows()
    ]
    return StopsResponse(stops=stops)


def _stop_wait(data: CorridorData, stop_id: int) -> pd.DataFrame:
    wait = data.wait[data.wait["표준버스정류장ID"] == stop_id]
    if wait.empty:
        raise HTTPException(status_code=404, detail=f"stop {stop_id} not found")
    return wait


def _current_hour() -> int:
    return datetime.now().hour


def _stop_capacity(data: CorridorData, stop_id: int) -> float:
    row = data.capacity[data.capacity["표준버스정류장ID"] == stop_id]
    return float(row["포용인원"].iloc[0])


@app.get("/stops/{stop_id}/congestion", response_model=CongestionResponse)
def get_congestion(
    stop_id: int,
    hour: int | None = Query(default=None, ge=0, le=23),
    data: CorridorData = Depends(get_corridor_data),
) -> CongestionResponse:
    """Estimated wait and congestion grade for one stop at one hour (default: current hour)."""
    wait = _stop_wait(data, stop_id)
    target_hour = _current_hour() if hour is None else hour
    row = wait[wait["시간대"] == target_hour]
    if row.empty:
        raise HTTPException(
            status_code=404, detail=f"hour {target_hour} not found for stop {stop_id}"
        )
    estimated_wait = float(row["W"].iloc[0])
    return CongestionResponse(
        stop_id=stop_id,
        name=str(row["정류장명"].iloc[0]),
        hour=target_hour,
        estimated_wait=estimated_wait,
        grade=grade_wait(estimated_wait, _stop_capacity(data, stop_id)),
    )


@app.get("/stops/{stop_id}/timeline", response_model=TimelineResponse)
def get_timeline(
    stop_id: int, data: CorridorData = Depends(get_corridor_data)
) -> TimelineResponse:
    """Full 24-hour estimated-wait curve for one stop, each hour graded."""
    wait = _stop_wait(data, stop_id).sort_values("시간대")
    capacity = _stop_capacity(data, stop_id)
    return TimelineResponse(
        stop_id=stop_id,
        name=str(wait["정류장명"].iloc[0]),
        timeline=[
            TimelinePoint(
                hour=int(row["시간대"]),
                estimated_wait=float(row["W"]),
                grade=grade_wait(float(row["W"]), capacity),
            )
            for _, row in wait.iterrows()
        ],
    )


@app.get("/corridor", response_model=CorridorResponse)
def get_corridor(
    hour: int | None = Query(default=None, ge=0, le=23),
    data: CorridorData = Depends(get_corridor_data),
) -> CorridorResponse:
    """Every stop's estimated wait at one hour (default: current hour)."""
    target_hour = _current_hour() if hour is None else hour
    snapshot = data.wait[data.wait["시간대"] == target_hour]
    stops = [
        CorridorStopSnapshot(
            stop_id=int(row["표준버스정류장ID"]),
            name=str(row["정류장명"]),
            estimated_wait=float(row["W"]),
        )
        for _, row in snapshot.iterrows()
    ]
    return CorridorResponse(hour=target_hour, stops=stops)
