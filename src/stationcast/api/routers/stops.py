"""Stop listing, per-stop timeline, and the corridor-wide snapshot.

/stops, /stops/{id}/timeline, /corridor added in S2 (issue #13).
"""

from fastapi import APIRouter, Depends, HTTPException, Query

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


def _parse_bbox(bbox: str) -> tuple[float, float, float, float]:
    parts = bbox.split(",")
    if len(parts) != 4:
        raise HTTPException(
            status_code=422, detail="bbox must be minlon,minlat,maxlon,maxlat"
        )
    try:
        minlon, minlat, maxlon, maxlat = (float(p) for p in parts)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="bbox must be minlon,minlat,maxlon,maxlat"
        ) from exc
    return minlon, minlat, maxlon, maxlat


@router.get("/stops", response_model=StopsResponse)
def list_stops(
    bbox: str | None = Query(default=None, description="minlon,minlat,maxlon,maxlat"),
    limit: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    data: CorridorData = Depends(get_corridor_data),
) -> StopsResponse:
    """List stops in the corridor, optionally viewport-filtered and paginated.

    No bbox/limit returns every stop, same as before -- both are opt-in so
    STATIONCAST_SCOPE=seoul's ~11,000 stops don't become a required query
    param for demo-scope callers that don't need them yet.
    """
    df = data.stops
    if bbox is not None:
        minlon, minlat, maxlon, maxlat = _parse_bbox(bbox)
        df = df[
            df["X좌표"].between(minlon, maxlon) & df["Y좌표"].between(minlat, maxlat)
        ]
    if limit is not None:
        df = df.iloc[offset : offset + limit]
    elif offset:
        df = df.iloc[offset:]

    stops = [
        Stop(
            stop_id=int(row["표준버스정류장ID"]),
            name=str(row["정류장명"]),
            ars_number=str(row["ARS번호"]),
            lat=float(row["Y좌표"]),
            lon=float(row["X좌표"]),
            stop_type=str(row["정류소 타입"]),
        )
        for row in df.to_dict("records")
    ]
    return StopsResponse(stops=stops)


@router.get("/stops/{stop_id}/timeline", response_model=TimelineResponse)
def get_timeline(stop_id: int, data: CorridorData = Depends(get_corridor_data)) -> TimelineResponse:
    """Full 24-hour estimated-wait curve for one stop, each hour graded."""
    # sort_index(), not sort_values("시간대") -- data.wait's index and its
    # (drop=False) columns share names, and sort_values("시간대") can't tell
    # which one is meant. The index's second level is 시간대 and the first
    # (표준버스정류장ID) is constant here, so sorting the index sorts by hour.
    wait = deps.stop_wait(data, stop_id).sort_index()
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
    """Every stop's estimated wait and congestion grade at one hour (default: current hour).

    data.wait's [표준버스정류장ID, 시간대] index (api/data.py) makes both the
    per-hour cross-section and each row's capacity lookup (deps.stop_capacity,
    now also indexed) O(1)-ish index lookups instead of full-table scans --
    the old per-row deps.stop_capacity() call made this endpoint O(stops²).
    """
    target_hour = deps.current_hour() if hour is None else hour
    try:
        snapshot = data.wait.xs(target_hour, level="시간대")
    except KeyError:
        snapshot = data.wait.iloc[:0]
    stops = [
        CorridorStopSnapshot(
            stop_id=(stop_id := int(row["표준버스정류장ID"])),
            name=str(row["정류장명"]),
            estimated_wait=(estimated_wait := float(row["W"])),
            grade=grade_wait(estimated_wait, deps.stop_capacity(data, stop_id)),
        )
        for row in snapshot.to_dict("records")
    ]
    return CorridorResponse(hour=target_hour, stops=stops)
