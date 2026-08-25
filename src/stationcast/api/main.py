"""FastAPI application entrypoint.

/stops, /stops/{id}/congestion, /stops/{id}/timeline, /corridor added in
S2 (issue #13). /stops/{id}/context added in S3 (issue #47).
"""

import asyncio
from datetime import datetime

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from stationcast.api.data import CorridorData, get_corridor_data
from stationcast.api.schemas import (
    ArrivalInfo,
    ArrivalsResponse,
    CongestionResponse,
    CorridorResponse,
    CorridorStopSnapshot,
    Stop,
    StopContextResponse,
    StopsResponse,
    TimelinePoint,
    TimelineResponse,
)
from stationcast.estimator.congestion import grade_wait
from stationcast.features.demand_factors import (
    boarding_factor,
    boarding_factor_for_labels,
    classify_day_type,
    classify_temperature,
    congestion_note,
    precipitation_type_from_asos,
)
from stationcast.ingest.realtime_arrival import ArrivalInfoUnavailable, fetch_arrivals
from stationcast.ingest.weather_forecast import (
    ForecastUnavailable,
    build_daily_forecast,
    fetch_forecast_items,
)

# Matches weather_forecast.py's own KMA call timeout (3.0s) -- /stops/{id}/context
# can fall back to that live call, observed up to 1.9s.
REQUEST_TIMEOUT_SECONDS = 3.0

app = FastAPI(title="Station Cast API")


@app.middleware("http")
async def enforce_request_timeout(request: Request, call_next):
    """Cut off any request that overruns the response-time budget (issue #18)."""
    try:
        return await asyncio.wait_for(call_next(request), timeout=REQUEST_TIMEOUT_SECONDS)
    except TimeoutError:
        return JSONResponse(status_code=504, content={"detail": "request timed out"})


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


def _current_date() -> int:
    return int(datetime.now().strftime("%Y%m%d"))


def _stop_capacity(data: CorridorData, stop_id: int) -> float:
    row = data.capacity[data.capacity["표준버스정류장ID"] == stop_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"stop {stop_id} not found")
    return float(row["포용인원"].iloc[0])


def _stop_name(data: CorridorData, stop_id: int) -> str:
    row = data.stops[data.stops["표준버스정류장ID"] == stop_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"stop {stop_id} not found")
    return str(row["정류장명"].iloc[0])


def _stop_ars_number(data: CorridorData, stop_id: int) -> str:
    row = data.stops[data.stops["표준버스정류장ID"] == stop_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"stop {stop_id} not found")
    return str(row["ARS번호"].iloc[0])


def _to_arrival_info(item: dict[str, str | None]) -> ArrivalInfo:
    return ArrivalInfo(
        route_name=item.get("busRouteAbrv") or "",
        route_id=item.get("busRouteId") or "",
        direction=item.get("adirection") or "",
        arrival_message_1=item.get("arrmsg1") or "",
        arrival_message_2=item.get("arrmsg2") or "",
        congestion_1=item.get("congestion1"),
        congestion_2=item.get("congestion2"),
    )


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
def get_timeline(stop_id: int, data: CorridorData = Depends(get_corridor_data)) -> TimelineResponse:
    """Full 24-hour estimated-wait curve for one stop, each hour graded."""
    wait = _stop_wait(data, stop_id).sort_values("시간대")
    capacity = _stop_capacity(data, stop_id)
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


@app.get("/corridor", response_model=CorridorResponse)
def get_corridor(
    hour: int | None = Query(default=None, ge=0, le=23),
    data: CorridorData = Depends(get_corridor_data),
) -> CorridorResponse:
    """Every stop's estimated wait and congestion grade at one hour (default: current hour)."""
    target_hour = _current_hour() if hour is None else hour
    snapshot = data.wait[data.wait["시간대"] == target_hour]
    stops = [
        CorridorStopSnapshot(
            stop_id=(stop_id := int(row["표준버스정류장ID"])),
            name=str(row["정류장명"]),
            estimated_wait=(estimated_wait := float(row["W"])),
            grade=grade_wait(estimated_wait, _stop_capacity(data, stop_id)),
        )
        for _, row in snapshot.iterrows()
    ]
    return CorridorResponse(hour=target_hour, stops=stops)


@app.get("/stops/{stop_id}/context", response_model=StopContextResponse)
def get_context(
    stop_id: int,
    date: int | None = Query(default=None),
    data: CorridorData = Depends(get_corridor_data),
) -> StopContextResponse:
    """Weather + day-type context for one stop on one date (default: today).

    Historical dates (within weather_daily.parquet's collection window) use
    observed ASOS data. Dates outside that window -- typically "오늘" once the
    window rolls past its end date -- fall back to KMA's short-range forecast
    (ingest/weather_forecast.py), flagged is_forecast=True.
    """
    name = _stop_name(data, stop_id)
    target_date = _current_date() if date is None else date
    day_type = classify_day_type(target_date, set(data.holiday["사용일자"]))

    weather_row = data.weather[data.weather["사용일자"] == target_date]
    if not weather_row.empty:
        precipitation = float(weather_row["강수량"].iloc[0])
        snowfall = float(weather_row["신적설"].iloc[0])
        factor = boarding_factor(
            data.features_daily, data.weekday_weather_factor, stop_id, target_date
        )
        return StopContextResponse(
            stop_id=stop_id,
            name=name,
            date=target_date,
            day_type=day_type,
            temperature=float(weather_row["평균기온"].iloc[0]),
            precipitation=precipitation,
            humidity=float(weather_row["습도"].iloc[0]),
            snowfall=snowfall,
            wind_speed=float(weather_row["평균풍속"].iloc[0]),
            precipitation_type=precipitation_type_from_asos(precipitation, snowfall),
            is_forecast=False,
            congestion_note=congestion_note(day_type, factor),
        )

    try:
        forecast = build_daily_forecast(fetch_forecast_items(), target_date)
    except ForecastUnavailable as exc:
        raise HTTPException(
            status_code=404, detail=f"weather for date {target_date} not found"
        ) from exc

    weekday_group = "평일" if day_type == "평일" else "주말+공휴일"
    weather_group = "강수" if forecast.is_precipitating else "맑음"
    temp_group = classify_temperature(forecast.high_temp)
    factor = boarding_factor_for_labels(
        data.weekday_weather_factor, stop_id, weekday_group, weather_group, temp_group
    )

    return StopContextResponse(
        stop_id=stop_id,
        name=name,
        date=target_date,
        day_type=day_type,
        temperature=forecast.temperature,
        precipitation=0.0,
        humidity=forecast.humidity,
        snowfall=0.0,
        wind_speed=forecast.wind_speed,
        precipitation_type=forecast.precipitation_type,
        is_forecast=True,
        congestion_note=congestion_note(day_type, factor),
    )


@app.get("/stops/{stop_id}/arrivals", response_model=ArrivalsResponse)
def get_arrivals(stop_id: int, data: CorridorData = Depends(get_corridor_data)) -> ArrivalsResponse:
    """
    Real-time next-arrival info for every route serving one stop (issue #48).
    Backed by Seoul TOPIS (ws.bus.go.kr) -- a live display feature.
    """
    name = _stop_name(data, stop_id)
    ars_number = _stop_ars_number(data, stop_id)

    try:
        items = fetch_arrivals(ars_number)
    except ArrivalInfoUnavailable:
        return ArrivalsResponse(
            stop_id=stop_id,
            name=name,
            available=False,
            message="일시적으로 도착정보를 가져올 수 없습니다.",
            arrivals=[],
        )

    return ArrivalsResponse(
        stop_id=stop_id,
        name=name,
        available=True,
        message=None,
        arrivals=[_to_arrival_info(item) for item in items],
    )
