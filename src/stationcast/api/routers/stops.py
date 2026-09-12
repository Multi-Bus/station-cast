"""Stop listing, per-stop timeline, and the corridor-wide snapshot.

/stops, /stops/{id}/timeline, /corridor added in S2 (issue #13).
"""

from fastapi import APIRouter, Depends, Query

from stationcast.api import deps
from stationcast.api.data import CorridorData, get_corridor_data
from stationcast.api.schemas import (
    CorridorResponse,
    CorridorStopSnapshot,
    Stop,
    StopsResponse,
    TimelinePoint,
    TimelineResponse,
)
from stationcast.estimator.congestion import grade_wait

router = APIRouter()


@router.get("/stops", response_model=StopsResponse)
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


@router.get("/stops/{stop_id}/timeline", response_model=TimelineResponse)
def get_timeline(stop_id: int, data: CorridorData = Depends(get_corridor_data)) -> TimelineResponse:
    """Full 24-hour estimated-wait curve for one stop, each hour graded."""
    wait = deps.stop_wait(data, stop_id).sort_values("시간대")
    capacity = deps.stop_capacity(data, stop_id)
    return TimelineResponse(
        stop_id=stop_id,
        name=str(wait["정류장명"].iloc[0]),
        timeline=[
            TimelinePoint(
                hour=int(row["시간대"]),
                estimated_wait=(wait_value := float(row["W"])),
                grade=grade_wait(wait_value, capacity),
            )
            for _, row in wait.iterrows()
        ],
    )


@router.get("/corridor", response_model=CorridorResponse)
def get_corridor(
    hour: int | None = Query(default=None, ge=0, le=23),
    data: CorridorData = Depends(get_corridor_data),
) -> CorridorResponse:
    """Every stop's estimated wait and congestion grade at one hour (default: current hour)."""
    target_hour = deps.current_hour() if hour is None else hour
    snapshot = data.wait[data.wait["시간대"] == target_hour]
    stops = [
        CorridorStopSnapshot(
            stop_id=(stop_id := int(row["표준버스정류장ID"])),
            name=str(row["정류장명"]),
            estimated_wait=(estimated_wait := float(row["W"])),
            grade=grade_wait(estimated_wait, deps.stop_capacity(data, stop_id)),
        )
        for _, row in snapshot.iterrows()
    ]
    return CorridorResponse(hour=target_hour, stops=stops)
