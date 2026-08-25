"""Build a small synthetic data/processed/ for smoke-testing the API (issue #141).

This script fabricates the minimum parquet set load_corridor_data() needs, using the corridor's
real stop IDs (so /stops/{id}/... paths are meaningful) with made-up
values everywhere else, so `docker run` can be checked end to end without
the real pipeline.

Not a substitute for the real pipeline: run scripts/build_processed.py
for anything that needs to reflect actual ridership.
"""

import sys
from pathlib import Path

import pandas as pd

from stationcast.ingest.stop_capacity import build_stop_capacity

# A Monday with no precipitation and a temperature inside demand_factors.py's
# "보통" band -- lands on the 평일/맑음/보통 baseline, whose correction factor
# is 1.0 by definition (features/demand_factors.py:boarding_factor_for_labels),
# so weekday_weather_factor doesn't need every group's columns filled in.
SMOKE_DATE = 20260105


def build_smoke_data(out_dir: Path) -> None:
    capacity = build_stop_capacity()
    stop_ids = capacity["표준버스정류장ID"].tolist()

    stops = pd.DataFrame(
        {
            "표준버스정류장ID": stop_ids,
            "정류장명": [f"스모크 정류장 {i}" for i in range(len(stop_ids))],
            "ARS번호": [f"{i:05d}" for i in range(len(stop_ids))],
            "X좌표": [126.98 for _ in stop_ids],
            "Y좌표": [37.57 for _ in stop_ids],
            "정류소 타입": ["중앙차로" for _ in stop_ids],
        }
    )

    wait = pd.DataFrame(
        {
            "표준버스정류장ID": [s for s in stop_ids for _ in range(24)],
            "정류장명": [f"스모크 정류장 {i}" for i in range(len(stop_ids)) for _ in range(24)],
            "시간대": [h for _ in stop_ids for h in range(24)],
            "W": [5.0 for _ in stop_ids for _ in range(24)],
        }
    )

    weather = pd.DataFrame(
        {
            "사용일자": [SMOKE_DATE],
            "평균기온": [18.0],
            "강수량": [0.0],
            "습도": [55.0],
            "신적설": [0.0],
            "평균풍속": [2.0],
        }
    )

    holiday = pd.DataFrame(
        {"사용일자": pd.Series([], dtype="int64"), "공휴일명": pd.Series([], dtype="str")}
    )

    features_daily = pd.DataFrame(
        {
            "표준버스정류장ID": stop_ids,
            "사용일자": [SMOKE_DATE for _ in stop_ids],
            "요일구분": ["평일" for _ in stop_ids],
            "날씨구분": ["맑음" for _ in stop_ids],
            "기온구분": ["보통" for _ in stop_ids],
        }
    )

    # Baseline (평일/맑음/보통) short-circuits to factor 1.0 before touching
    # this table's columns (see SMOKE_DATE's comment), so no 보정계수_* columns
    # are needed -- just the stop IDs, to match how the real file is keyed.
    weekday_weather_factor = pd.DataFrame({"표준버스정류장ID": stop_ids})

    out_dir.mkdir(parents=True, exist_ok=True)
    stops.to_parquet(out_dir / "corridor_stops.parquet", index=False)
    wait.to_parquet(out_dir / "corridor_wait.parquet", index=False)
    weather.to_parquet(out_dir / "weather_daily.parquet", index=False)
    holiday.to_parquet(out_dir / "holiday_daily_all.parquet", index=False)
    features_daily.to_parquet(out_dir / "corridor_features_daily.parquet", index=False)
    weekday_weather_factor.to_parquet(out_dir / "weekday_weather_factor.parquet", index=False)


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/processed")
    build_smoke_data(out_dir)
    print(f"스모크 데이터 생성 완료 -> {out_dir}/ (실데이터 아님, 컨테이너 기동 확인 전용)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
