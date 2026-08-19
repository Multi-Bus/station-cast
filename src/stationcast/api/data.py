"""Corridor data loading for API endpoints (S2, issue #13).

data/processed/*.parquet is not committed (see data/README.md §8) -- each
teammate regenerates it locally by running the ingest/estimator pipeline.
Endpoints depend on get_corridor_data() via FastAPI's Depends so tests can
override it with in-memory fixtures instead of touching disk.

``wait`` reads corridor_wait.parquet, the per-route wait-population
estimate (estimator/wait_population.py). ``capacity`` comes from the field survey's
build_stop_capacity() (issue #12) rather than a parquet file, since it's
a plain in-memory constant with no ingest step to run.

``weather``, ``holiday``, ``features_daily``, ``weekday_weather_factor``
back the /stops/{id}/context endpoint (issue #47, #78) and are the direct
parquet outputs of features/demand_factors.py (issue #10, #69):
- weather: 사용일자·평균기온·강수량·습도·신적설·평균풍속
- holiday: 사용일자·공휴일명
- features_daily: 표준버스정류장ID·사용일자·요일구분·날씨구분·기온구분 등
  (요일×날씨×기온 라벨 조회용 -- 12그룹 보정계수의 컬럼명을 구성하는 데 씀)
- weekday_weather_factor: 표준버스정류장ID·정류장명·요일구분×날씨구분×기온구분
  (12그룹)별 보정계수_승차·보정계수_하차 등
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from stationcast.ingest.stop_capacity import build_stop_capacity

DATA_DIR = Path("data/processed")


@dataclass
class CorridorData:
    """
    stops: 표준버스정류장ID·정류장명·ARS번호·X좌표·Y좌표·정류소 타입 (corridor_stops.parquet)
    wait: 표준버스정류장ID·정류장명·시간대·W (corridor_wait.parquet)
    capacity: 표준버스정류장ID·포용인원 (build_stop_capacity())
    weather: 사용일자·평균기온·강수량·습도·신적설·평균풍속 (weather_daily.parquet)
    holiday: 사용일자·공휴일명 (holiday_daily.parquet)
    features_daily: 표준버스정류장ID·사용일자·요일구분·날씨구분·기온구분 등
        (corridor_features_daily.parquet)
    weekday_weather_factor: 표준버스정류장ID·보정계수_승차_<요일구분>_<날씨구분>_<기온구분> 등
        (weekday_weather_factor.parquet)
    """

    stops: pd.DataFrame
    wait: pd.DataFrame
    capacity: pd.DataFrame
    weather: pd.DataFrame
    holiday: pd.DataFrame
    features_daily: pd.DataFrame
    weekday_weather_factor: pd.DataFrame


def load_corridor_data(data_dir: Path = DATA_DIR) -> CorridorData:
    """Read the corridor's stop metadata and estimated-wait time series from disk."""
    stops = pd.read_parquet(data_dir / "corridor_stops.parquet")
    wait = pd.read_parquet(data_dir / "corridor_wait.parquet")
    capacity = build_stop_capacity()
    weather = pd.read_parquet(data_dir / "weather_daily.parquet")
    holiday = pd.read_parquet(data_dir / "holiday_daily.parquet")
    features_daily = pd.read_parquet(data_dir / "corridor_features_daily.parquet")
    weekday_weather_factor = pd.read_parquet(data_dir / "weekday_weather_factor.parquet")
    return CorridorData(
        stops=stops,
        wait=wait,
        capacity=capacity,
        weather=weather,
        holiday=holiday,
        features_daily=features_daily,
        weekday_weather_factor=weekday_weather_factor,
    )


def get_corridor_data() -> CorridorData:
    """FastAPI dependency wrapper around load_corridor_data(); override in tests."""
    return load_corridor_data()
