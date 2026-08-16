"""Corridor data loading for API endpoints (S2, issue #13).

data/processed/*.parquet is not committed (see data/README.md §8) -- each
teammate regenerates it locally by running the ingest/estimator pipeline.
Endpoints depend on get_corridor_data() via FastAPI's Depends so tests can
override it with in-memory fixtures instead of touching disk.

``wait`` reads corridor_wait_scipy.parquet, the SciPy-refined W(s,t)
estimate (issue #11). ``capacity`` comes from the field survey's
build_stop_capacity() (issue #12) rather than a parquet file, since it's
a plain in-memory constant with no ingest step to run.

``weather``, ``holiday``, ``weekday_holiday_factor`` back the
/stops/{id}/context endpoint (issue #47) and are the direct parquet
outputs of features/demand_factors.py (issue #10):
- weather: 사용일자·평균기온·강수량·습도·신적설·평균풍속
- holiday: 사용일자·공휴일명
- weekday_holiday_factor: 표준버스정류장ID·정류장명·보정계수_승차·보정계수_하차 등
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
    wait: 표준버스정류장ID·정류장명·시간대·W (corridor_wait_scipy.parquet)
    capacity: 표준버스정류장ID·포용인원 (build_stop_capacity())
    weather: 사용일자·평균기온·강수량·습도·신적설·평균풍속 (weather_daily.parquet)
    holiday: 사용일자·공휴일명 (holiday_daily.parquet)
    weekday_holiday_factor: 표준버스정류장ID·보정계수_승차 등 (weekday_holiday_factor.parquet)
    """

    stops: pd.DataFrame
    wait: pd.DataFrame
    capacity: pd.DataFrame
    weather: pd.DataFrame
    holiday: pd.DataFrame
    weekday_holiday_factor: pd.DataFrame


def load_corridor_data(data_dir: Path = DATA_DIR) -> CorridorData:
    """Read the corridor's stop metadata and estimated-wait time series from disk."""
    stops = pd.read_parquet(data_dir / "corridor_stops.parquet")
    wait = pd.read_parquet(data_dir / "corridor_wait_scipy.parquet")
    capacity = build_stop_capacity()
    weather = pd.read_parquet(data_dir / "weather_daily.parquet")
    holiday = pd.read_parquet(data_dir / "holiday_daily.parquet")
    weekday_holiday_factor = pd.read_parquet(data_dir / "weekday_holiday_factor.parquet")
    return CorridorData(
        stops=stops,
        wait=wait,
        capacity=capacity,
        weather=weather,
        holiday=holiday,
        weekday_holiday_factor=weekday_holiday_factor,
    )


def get_corridor_data() -> CorridorData:
    """FastAPI dependency wrapper around load_corridor_data(); override in tests."""
    return load_corridor_data()
