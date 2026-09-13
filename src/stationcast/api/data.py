"""Corridor data loading for API endpoints (S2, issue #13).

data/processed/*.parquet is committed (only data/raw/ is ignored -- see
data/README.md §11), so a checkout and the container image both start with
data. Endpoints depend on get_corridor_data() via FastAPI's Depends so tests can
override it with in-memory fixtures instead of touching disk.

``wait`` reads corridor_wait.parquet, the per-route wait-population
estimate (estimator/wait_population.py). ``grade_thresholds`` reads
grade_thresholds.parquet, the Seoul-wide (p70, p90) cutoffs
estimator/congestion.py derives from that same W distribution -- one row,
not a per-stop table, since grading is now relative to all of Seoul rather
than to each stop's own field-surveyed 포용인원.

``weather``, ``holiday``, ``weekday_weather_factor`` back the
/stops/{id}/context endpoint (issue #47, #78) and are the direct parquet
outputs of features/demand_factors.py and ingest/holiday.py:
- weather: 사용일자·평균기온·최고기온·강수량·습도·신적설·평균풍속 등
  (weather_daily.parquet)
- holiday: 사용일자·공휴일명 (holiday_daily_all.parquet, 범위 무제한)
- weekday_weather_factor: 표준버스정류장ID·정류장명·요일구분×날씨구분×기온구분
  (12그룹)별 보정계수_승차·보정계수_하차 등

corridor_features_daily.parquet is deliberately *not* loaded. It is
corridor_daily joined with the 요일구분/날씨구분/기온구분 labels, and the
API only ever read it to look those three labels up for one (stop, date).
Those labels are a function of the date alone -- weather_daily is a single
city-wide observation station, so every stop on a given date carries
identical labels (verified over all 23,015 rows: exactly one distinct
value per date for each of the three columns, and recomputing them the way
this endpoint now does matches the stored labels on every row) -- so
routers/congestion.py derives them from ``weather`` and ``holiday``
instead, the same way its forecast branch already did. At
STATIONCAST_SCOPE=seoul the table would be ~11,000 stops x ~1,100 days
~= 12M rows (~1.8GB resident per worker, extrapolated from 3.45MB for the
21-stop demo scope), by far the largest thing the API would hold;
validate/boarding_reproduction.py still reads the file from disk.

stops/wait are indexed by 표준버스정류장ID (wait also by 시간대,
CorridorData.__post_init__) so api/deps.py's per-stop lookups are a
``.loc[]`` index lookup instead of a boolean-mask scan over every row -- at
demo scope (21 stops) the difference is noise, but /corridor does one
lookup per stop per request, so an unindexed scan is O(stops²) and that
stops being true well before STATIONCAST_SCOPE=seoul's ~11,000 stops.
Indexing lives on the dataclass rather than in
load_corridor_data() so tests that build a CorridorData directly (see
tests/test_api_stops.py's fixture) get the same indexing without having to
remember to do it themselves.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from fastapi import Request

DATA_DIR = Path("data/processed")

_PARQUET_FILES = (
    "corridor_stops.parquet",
    "corridor_wait.parquet",
    "grade_thresholds.parquet",
    "weather_daily.parquet",
    "holiday_daily_all.parquet",
    "weekday_weather_factor.parquet",
)


class CorridorDataUnavailable(Exception):
    """Raised when data_dir is missing one of the parquet files
    load_corridor_data() needs -- most commonly a container run without the
    data volume mounted. Callers should surface this as a 503, not a 500:
    the service isn't broken, it just hasn't been given its data yet."""


@dataclass
class CorridorData:
    """
    stops: 표준버스정류장ID·정류장명·ARS번호·X좌표·Y좌표·정류소 타입 (corridor_stops.parquet)
    wait: 표준버스정류장ID·정류장명·시간대·W (corridor_wait.parquet)
    grade_thresholds: p70·p90 1행 (grade_thresholds.parquet)
    weather: 사용일자·평균기온·최고기온·강수량·습도·신적설·평균풍속 등
        (weather_daily.parquet)
    holiday: 사용일자·공휴일명 (holiday_daily_all.parquet, 범위 무제한)
    weekday_weather_factor: 표준버스정류장ID·보정계수_승차_<요일구분>_<날씨구분>_<기온구분> 등
        (weekday_weather_factor.parquet)
    """

    stops: pd.DataFrame
    wait: pd.DataFrame
    grade_thresholds: pd.DataFrame
    weather: pd.DataFrame
    holiday: pd.DataFrame
    weekday_weather_factor: pd.DataFrame

    def __post_init__(self) -> None:
        self.stops = self.stops.set_index("표준버스정류장ID", drop=False)
        self.wait = self.wait.set_index(["표준버스정류장ID", "시간대"], drop=False).sort_index()


def load_corridor_data(data_dir: Path = DATA_DIR) -> CorridorData:
    """Read the corridor's stop metadata and estimated-wait time series from disk.

    Raises CorridorDataUnavailable listing every missing file, rather than
    letting the first pd.read_parquet() fail with a bare FileNotFoundError --
    someone bringing up a fresh container wants the whole list at once, not
    one file per restart.
    """
    missing = [name for name in _PARQUET_FILES if not (data_dir / name).exists()]
    if missing:
        raise CorridorDataUnavailable(
            f"missing parquet files in {data_dir}: {missing} -- run "
            "scripts/build_processed.py and estimator/wait_population.py, "
            "or mount a data/processed/ directory that already has them"
        )

    stops = pd.read_parquet(data_dir / "corridor_stops.parquet")
    wait = pd.read_parquet(data_dir / "corridor_wait.parquet")
    grade_thresholds = pd.read_parquet(data_dir / "grade_thresholds.parquet")
    weather = pd.read_parquet(data_dir / "weather_daily.parquet")
    holiday = pd.read_parquet(data_dir / "holiday_daily_all.parquet")
    weekday_weather_factor = pd.read_parquet(data_dir / "weekday_weather_factor.parquet")
    return CorridorData(
        stops=stops,
        wait=wait,
        grade_thresholds=grade_thresholds,
        weather=weather,
        holiday=holiday,
        weekday_weather_factor=weekday_weather_factor,
    )


def get_corridor_data(request: Request) -> CorridorData:
    """FastAPI dependency reading the data api/main.py's lifespan loaded once
    at startup; override in tests via app.dependency_overrides.

    Loading used to happen lazily on the first request (behind an
    lru_cache) -- issue #114 fixed the *n* extra reloads that caused, but
    the very first request still paid the full load cost inline, which
    risked tripping REQUEST_TIMEOUT_SECONDS once STATIONCAST_SCOPE=seoul
    makes that cost much bigger. Loading at startup instead means every
    request just reads an attribute.

    Raises CorridorDataUnavailable (-> 503 via main.py's exception handler)
    if startup couldn't load the data, e.g. a container started without the
    data volume mounted (issue #141) -- the lifespan captures that error
    instead of letting it fail startup, so /health still responds and other
    routes degrade to 503 instead of the whole app failing to come up.
    """
    error = getattr(request.app.state, "corridor_data_error", None)
    if error is not None:
        raise error
    return request.app.state.corridor_data
