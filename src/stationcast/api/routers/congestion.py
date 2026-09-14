"""Per-stop congestion estimate and the weather/day-type context behind it.

/stops/{id}/congestion added in S2 (issue #13); /stops/{id}/context in S3 (issue #47).
"""

from dataclasses import dataclass

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from stationcast.api import deps
from stationcast.api.data import CorridorData, get_corridor_data
from stationcast.api.schemas import CongestionResponse, StopContextResponse
from stationcast.estimator.congestion import grade_wait
from stationcast.features.demand_factors import (
    BoardingFactorUnavailable,
    boarding_factor_for_labels,
    classify_day_type,
    classify_temperature,
    congestion_note,
    normalized_boarding_factor_for_labels,
    precipitation_type_from_asos,
)
from stationcast.ingest.weather_forecast import (
    ForecastUnavailable,
    build_daily_forecast,
    fetch_forecast_items,
)

router = APIRouter()


@dataclass
class _Weather:
    """One date's weather, from observed ASOS or a forecast, plus the
    (요일구분, 날씨구분, 기온구분) labels the correction factors are keyed by."""

    day_type: str
    labels: tuple[str, str, str]
    temperature: float
    precipitation: float
    humidity: float
    snowfall: float
    wind_speed: float | None
    precipitation_type: str
    is_forecast: bool


def _resolve_weather(data: CorridorData, target_date: int) -> _Weather:
    """Weather for one date: observed ASOS if the date is inside
    weather_daily.parquet's window, else KMA's short-range forecast.

    Raises ForecastUnavailable when neither is available -- /context turns
    that into a 404, /congestion degrades to an uncorrected estimate.

    요일·날씨·기온 라벨은 **날짜만의 함수**라(weather_daily가 서울 전체 단일
    관측소) 여기서 바로 유도한다. 예전에는 정류장×일자로 미리 계산해둔
    corridor_features_daily에서 같은 라벨을 조회했는데, 서울 전체 스코프에서
    12M행짜리 테이블을 문자열 3개 때문에 상주시키게 되어 걷어냈다
    (api/data.py 참고).
    """
    day_type = classify_day_type(target_date, set(data.holiday["사용일자"]))
    # 보정계수 테이블은 평일/주말+공휴일 2분류로 묶여 있어 공휴일과 주말이 한 그룹.
    weekday_group = "평일" if day_type == "평일" else "주말+공휴일"

    weather_row = data.weather[data.weather["사용일자"] == target_date]
    if not weather_row.empty:
        precipitation = float(weather_row["강수량"].iloc[0])
        snowfall = float(weather_row["신적설"].iloc[0])
        raw_wind_speed = weather_row["평균풍속"].iloc[0]
        return _Weather(
            day_type=day_type,
            labels=(
                weekday_group,
                "강수" if precipitation > 0 or snowfall > 0 else "맑음",
                classify_temperature(float(weather_row["최고기온"].iloc[0])),
            ),
            temperature=float(weather_row["평균기온"].iloc[0]),
            precipitation=precipitation,
            humidity=float(weather_row["습도"].iloc[0]),
            snowfall=snowfall,
            wind_speed=None if pd.isna(raw_wind_speed) else float(raw_wind_speed),
            precipitation_type=precipitation_type_from_asos(precipitation, snowfall),
            is_forecast=False,
        )

    forecast = build_daily_forecast(fetch_forecast_items(), target_date)
    return _Weather(
        day_type=day_type,
        labels=(
            weekday_group,
            "강수" if forecast.is_precipitating else "맑음",
            classify_temperature(forecast.high_temp),
        ),
        temperature=forecast.temperature,
        precipitation=0.0,
        humidity=forecast.humidity,
        snowfall=0.0,
        wind_speed=forecast.wind_speed,
        precipitation_type=forecast.precipitation_type,
        is_forecast=True,
    )


@router.get("/stops/{stop_id}/congestion", response_model=CongestionResponse)
def get_congestion(
    stop_id: int,
    hour: int | None = Query(default=None, ge=0, le=23),
    date: int | None = Query(default=None),
    data: CorridorData = Depends(get_corridor_data),
) -> CongestionResponse:
    """Estimated wait and congestion grade for one stop at one hour (default: current hour).

    corridor_wait.parquet's W is an average over every weekday and weather
    condition, so it is scaled here by that date's 보정계수_승차_정규화 --
    the same correction /context has always *described* in prose but never
    applied to the number next to it. weather_applied=False means no factor
    was available (unknown stop-group combination, or no weather for the
    date at all) and the estimate is the uncorrected average; the estimate is
    never withheld over a missing correction.
    """
    wait = deps.stop_wait(data, stop_id)
    target_hour = deps.current_hour() if hour is None else hour
    row = wait[wait["시간대"] == target_hour]
    if row.empty:
        raise HTTPException(
            status_code=404, detail=f"hour {target_hour} not found for stop {stop_id}"
        )
    estimated_wait = float(row["W"].iloc[0])

    target_date = deps.current_date() if date is None else date
    deps.validate_date(target_date)
    try:
        weather = _resolve_weather(data, target_date)
        factor = normalized_boarding_factor_for_labels(
            data.weekday_weather_factor, stop_id, *weather.labels
        )
    except (ForecastUnavailable, BoardingFactorUnavailable):
        weather_applied = False
    else:
        estimated_wait *= factor
        weather_applied = True

    return CongestionResponse(
        stop_id=stop_id,
        name=str(row["정류장명"].iloc[0]),
        hour=target_hour,
        estimated_wait=estimated_wait,
        grade=grade_wait(estimated_wait, deps.grade_thresholds(data)),
        grade_basis="seoul_percentile",
        weather_applied=weather_applied,
    )


@router.get("/stops/{stop_id}/context", response_model=StopContextResponse)
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
    name = deps.stop_name(data, stop_id)
    target_date = deps.current_date() if date is None else date
    deps.validate_date(target_date)

    try:
        weather = _resolve_weather(data, target_date)
    except ForecastUnavailable as exc:
        raise HTTPException(
            status_code=404, detail=f"weather for date {target_date} not found"
        ) from exc

    try:
        # 설명 문구는 기준선(평일·맑음·보통) 대비 비율을 그대로 읽어준다 --
        # "평소보다 15% 낮다"는 말의 기준이 곧 그 기준선이라, W에 곱하는
        # 정규화 계수와는 다른 값을 써야 한다.
        factor = boarding_factor_for_labels(
            data.weekday_weather_factor, stop_id, *weather.labels
        )
    except BoardingFactorUnavailable as exc:
        raise HTTPException(
            status_code=404, detail=f"no correction factor for stop {stop_id} on {target_date}"
        ) from exc

    return StopContextResponse(
        stop_id=stop_id,
        name=name,
        date=target_date,
        day_type=weather.day_type,
        temperature=weather.temperature,
        precipitation=weather.precipitation,
        humidity=weather.humidity,
        snowfall=weather.snowfall,
        wind_speed=weather.wind_speed,
        precipitation_type=weather.precipitation_type,
        is_forecast=weather.is_forecast,
        congestion_note=congestion_note(weather.day_type, factor),
    )
