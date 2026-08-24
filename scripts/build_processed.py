"""Rebuild every A-track data/processed/ parquet from data/raw/ in one run (issue #20).

Downloading the raw files stays manual -- 기상청 needs a login and 특일정보
needs an API key (see data/README.md §1~§7). This script covers everything
after that, so a teammate with a populated data/raw/ can regenerate the whole
A-track pipeline with one command:

    python scripts/build_processed.py

Inputs are resolved by pattern rather than fixed paths: the 기상청 file's name
carries its download timestamp and the OA-12912 monthly CSVs live in their own
subdirectory, so the per-module ``__main__`` blocks (weather.py's
``data/raw/weather.csv``, oa12912.py's ``data/raw``) point at paths the real
layout doesn't use. Every resolved input is printed so a run says exactly which
files produced its output.

Scope is A-track only (ingest + features). estimator/wait_population.py, which
turns these into corridor_wait.parquet, is B-track and runs separately.
"""

import sys
import time
from collections.abc import Callable
from pathlib import Path

from stationcast.features.demand_factors import run as run_demand_factors
from stationcast.ingest.holiday import run as run_holiday
from stationcast.ingest.oa12912 import run as run_oa12912
from stationcast.ingest.oa12913 import run as run_oa12913
from stationcast.ingest.route_schedule import run as run_route_schedule
from stationcast.ingest.stop_capacity import run as run_stop_capacity
from stationcast.ingest.weather import run as run_weather

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
BOARDING_MONTH_DIR = RAW_DIR / "BUS_STATION_BOARDING_MONTH"

WEATHER_GLOB = "OBS_ASOS_DD_*.csv"
HOLIDAY_GLOB = "SPCDE_HOLIDAY_*.csv"
BOARDING_MONTH_GLOB = "BUS_STATION_BOARDING_MONTH_*.csv"
HOURLY_BOARDING_GLOB = "*버스노선별_정류장별_시간대별_승하차*.csv"
STOP_COORD_GLOB = "*버스정류소*위치정보*.csv"
ROUTE_SCHEDULE_GLOB = "*버스노선기본정보*.xlsx"

REQUIRED_INPUTS: list[tuple[Path, str, str]] = [
    (RAW_DIR, HOURLY_BOARDING_GLOB, "데이터셋① OA-12913 시간대별 승하차 (data/README.md §1)"),
    (RAW_DIR, STOP_COORD_GLOB, "데이터셋② 버스정류소 위치정보 (data/README.md §2)"),
    (BOARDING_MONTH_DIR, BOARDING_MONTH_GLOB, "데이터셋③ OA-12912 일별 승하차 (data/README.md §3)"),
    (RAW_DIR, WEATHER_GLOB, "데이터셋④ 기상청 ASOS 일자료 (data/README.md §4)"),
    (RAW_DIR, HOLIDAY_GLOB, "데이터셋⑤ 특일 정보 (data/README.md §5)"),
    (RAW_DIR, ROUTE_SCHEDULE_GLOB, "데이터셋⑦ 서울시 버스운행노선 정보 (data/README.md §7)"),
]


def missing_inputs() -> list[str]:
    """Describe every required raw input that data/raw/ doesn't have yet.

    Reports all of them at once rather than dying on the first: someone
    setting up from scratch should see the whole download list in one go.
    """
    return [
        f"{description}: {directory}/{pattern}"
        for directory, pattern, description in REQUIRED_INPUTS
        if not sorted(directory.glob(pattern))
    ]


def newest_match(directory: Path, pattern: str) -> Path:
    """Pick the newest file matching ``pattern``, by filename.

    The 기상청 download names files OBS_ASOS_DD_<yyyymmddhhmmss>.csv, so a
    re-download leaves the superseded file sitting next to the new one and
    the timestamps sort chronologically. Taking the newest keeps a stale
    download from silently becoming the pipeline's input.
    """
    return max(sorted(directory.glob(pattern)))


def main() -> int:
    missing = missing_inputs()
    if missing:
        print("data/raw/에 필요한 원본 파일이 없습니다:", file=sys.stderr)
        for line in missing:
            print(f"  - {line}", file=sys.stderr)
        print(
            "\n원본 파일 확보 방법은 data/README.md의 각 데이터셋 절을 참고하세요.", file=sys.stderr
        )
        return 1

    weather_csv = newest_match(RAW_DIR, WEATHER_GLOB)
    holiday_csv = newest_match(RAW_DIR, HOLIDAY_GLOB)
    month_count = len(sorted(BOARDING_MONTH_DIR.glob(BOARDING_MONTH_GLOB)))

    print(f"입력: {weather_csv}")
    print(f"입력: {holiday_csv}")
    print(f"입력: {BOARDING_MONTH_DIR}/ (월별 CSV {month_count}개)")
    print(f"출력: {PROCESSED_DIR}/\n")

    # oa12913/oa12912/route_schedule/weather/holiday/stop_capacity read only
    # data/raw, so their order is free; demand_factors runs last because it
    # reads corridor_daily/weather_daily/holiday_daily back out of
    # data/processed.
    steps: list[tuple[str, Callable[[], None]]] = [
        ("corridor_route_hourly, corridor_stops", lambda: run_oa12913(RAW_DIR, PROCESSED_DIR)),
        ("corridor_daily", lambda: run_oa12912(BOARDING_MONTH_DIR, PROCESSED_DIR)),
        ("corridor_route_schedule", lambda: run_route_schedule(RAW_DIR, PROCESSED_DIR)),
        ("weather_daily", lambda: run_weather(weather_csv, PROCESSED_DIR)),
        ("holiday_daily, holiday_daily_all", lambda: run_holiday(holiday_csv, PROCESSED_DIR)),
        ("stop_capacity", lambda: run_stop_capacity(PROCESSED_DIR)),
        (
            "corridor_features_daily, weekday_weather_factor",
            lambda: run_demand_factors(PROCESSED_DIR),
        ),
    ]

    started = time.perf_counter()
    for index, (label, step) in enumerate(steps, start=1):
        step_started = time.perf_counter()
        print(f"[{index}/{len(steps)}] {label} ...", flush=True)
        step()
        print(f"      완료 ({time.perf_counter() - step_started:.1f}초)")

    print(f"\n전체 완료 ({time.perf_counter() - started:.1f}초) -> {PROCESSED_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
