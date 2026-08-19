"""FastAPI application entrypoint.

/stops, /stops/{id}/congestion, /stops/{id}/timeline, /corridor added in
S2 (issue #13). /stops/{id}/context added in S3 (issue #47).
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
    StopContextResponse,
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


def _current_date() -> int:
    return int(datetime.now().strftime("%Y%m%d"))


def _stop_capacity(data: CorridorData, stop_id: int) -> float:
    row = data.capacity[data.capacity["표준버스정류장ID"] == stop_id]
    return float(row["포용인원"].iloc[0])


def _stop_name(data: CorridorData, stop_id: int) -> str:
    row = data.stops[data.stops["표준버스정류장ID"] == stop_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"stop {stop_id} not found")
    return str(row["정류장명"].iloc[0])


def _boarding_factor(data: CorridorData, stop_id: int, date: int) -> float:
    features_row = data.features_daily[
        (data.features_daily["표준버스정류장ID"] == stop_id)
        & (data.features_daily["사용일자"] == date)
    ].iloc[0]
    weekday_group = str(features_row["요일구분"])
    weather_group = str(features_row["날씨구분"])
    temp_group = str(features_row["기온구분"])

    if (weekday_group, weather_group, temp_group) == ("평일", "맑음", "보통"):
        return 1.0

    factor_row = data.weekday_weather_factor[
        data.weekday_weather_factor["표준버스정류장ID"] == stop_id
    ]
    column = f"보정계수_승차_{weekday_group}_{weather_group}_{temp_group}"
    return float(factor_row[column].iloc[0])


def _day_type(date: int, holiday_dates: set[int]) -> str:
    """Classify a date as 공휴일 > 주말 > 평일 (holiday takes priority over weekend)."""
    if date in holiday_dates:
        return "공휴일"
    dow = pd.to_datetime(str(date), format="%Y%m%d").dayofweek
    return "주말" if dow >= 5 else "평일"


def _congestion_note(day_type: str, boarding_factor: float) -> str:
    """Human-readable explanation of the day-type correction factor.

    boarding_factor is 보정계수_승차 (해당 요일×날씨×기온 그룹 평균승차 / 기준선
    평균승차) from weekday_weather_factor.parquet, via _boarding_factor()
    """
    if day_type == "평일":
        return "평일이라 평소와 비슷한 혼잡도가 예상됩니다."
    percent = round(abs(boarding_factor - 1.0) * 100)
    direction = "낮을" if boarding_factor < 1.0 else "높을"
    return f"{day_type}이라 평소보다 혼잡도가 약 {percent}% {direction} 것으로 예상됩니다."


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


@app.get("/stops/{stop_id}/context", response_model=StopContextResponse)
def get_context(
    stop_id: int,
    date: int | None = Query(default=None),
    data: CorridorData = Depends(get_corridor_data),
) -> StopContextResponse:
    """Weather + day-type context for one stop on one date (default: today)."""
    name = _stop_name(data, stop_id)
    target_date = _current_date() if date is None else date

    weather_row = data.weather[data.weather["사용일자"] == target_date]
    if weather_row.empty:
        raise HTTPException(status_code=404, detail=f"weather for date {target_date} not found")

    day_type = _day_type(target_date, set(data.holiday["사용일자"]))
    boarding_factor = _boarding_factor(data, stop_id, target_date)

    return StopContextResponse(
        stop_id=stop_id,
        name=name,
        date=target_date,
        day_type=day_type,
        temperature=float(weather_row["평균기온"].iloc[0]),
        precipitation=float(weather_row["강수량"].iloc[0]),
        humidity=float(weather_row["습도"].iloc[0]),
        snowfall=float(weather_row["신적설"].iloc[0]),
        wind_speed=float(weather_row["평균풍속"].iloc[0]),
        congestion_note=_congestion_note(day_type, boarding_factor),
    )
