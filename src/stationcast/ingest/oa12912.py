"""OA-12912 daily boarding/alighting collector.

Complements oa12913.py (hourly, monthly-aggregated) with per-date
granularity for the same Jongno-Myeongdong-Euljiro corridor. Used by
features/ (issue #10) to derive weekday/weekend/holiday/seasonal
correction factors, since OA-12913 alone has no per-date breakdown.
"""

import re
from pathlib import Path

import pandas as pd

from stationcast.ingest.oa12913 import CORRIDOR_NIGHT_BUS_ROUTES, CORRIDOR_STOP_IDS

_NAME_SUFFIX_RE = re.compile(r"\(\d+\)$")


def _clean_stop_name(name: object) -> str:
    """Strip the trailing per-route sequence number from a raw 역명 value."""
    return _NAME_SUFFIX_RE.sub("", str(name))


def load_daily_boarding(csv_path: Path) -> pd.DataFrame:
    """Load one month's raw OA-12912 CSV (cp949-encoded)."""
    return pd.read_csv(csv_path, encoding="cp949", low_memory=False)


def build_corridor_daily(
    boarding_df: pd.DataFrame, stop_ids: tuple[int, ...] = CORRIDOR_STOP_IDS
) -> pd.DataFrame:
    """Aggregate route-level daily rows into stop x date boarding/alighting totals.

    Sums across every route serving a stop, same rationale as
    build_corridor_hourly in oa12913.py: the queue balance model is
    stop-scoped, not route-scoped. ``boarding_df`` may span multiple
    months concatenated together (see run()).

    Grouped by 표준버스정류장ID alone (not also by name): a stop's
    registered name can change mid-period (e.g., ID 101000042 was renamed
    from 해운센터.롯데영플라자 to 소공동.롯데영플라자 on 2026-05-11 within
    the 12-month history), and grouping by name too would split one
    physical stop's continuous series into two. The most recent name is
    attached afterward as a single representative label.

    Excludes CORRIDOR_NIGHT_BUS_ROUTES (same exclusion as
    build_corridor_hourly in oa12913.py) -- this dataset has no
    교통수단타입명 column, so night-bus routes are filtered by number here
    instead.
    """
    sub = boarding_df[boarding_df["표준버스정류장ID"].isin(stop_ids)].copy()
    sub = sub[~sub["노선번호"].astype(str).isin(CORRIDOR_NIGHT_BUS_ROUTES)]
    sub["정류장명"] = sub["역명"].apply(_clean_stop_name)

    daily_totals = (
        sub.groupby(["표준버스정류장ID", "사용일자"])
        .agg(승차=("승차총승객수", "sum"), 하차=("하차총승객수", "sum"))
        .reset_index()
    )
    latest_name = (
        sub.sort_values("사용일자").groupby("표준버스정류장ID")["정류장명"].last()
    )
    result = daily_totals.merge(latest_name, on="표준버스정류장ID", how="left")

    return (
        result[["표준버스정류장ID", "정류장명", "사용일자", "승차", "하차"]]
        .sort_values(["표준버스정류장ID", "사용일자"])
        .reset_index(drop=True)
    )


def run(raw_dir: Path, out_dir: Path) -> None:
    """Build corridor_daily.parquet from every OA-12912 monthly CSV in raw_dir.

    Picks up all files matching ``BUS_STATION_BOARDING_MONTH_*.csv`` so
    additional months can be dropped into raw_dir and reprocessed without
    code changes.
    """
    csv_paths = sorted(raw_dir.glob("BUS_STATION_BOARDING_MONTH_*.csv"))
    if not csv_paths:
        raise FileNotFoundError(f"No OA-12912 monthly CSVs found in {raw_dir}")

    monthly_frames = [load_daily_boarding(p) for p in csv_paths]
    combined = pd.concat(monthly_frames, ignore_index=True)
    daily = build_corridor_daily(combined)

    out_dir.mkdir(parents=True, exist_ok=True)
    daily.to_parquet(out_dir / "corridor_daily.parquet", index=False)


if __name__ == "__main__":
    run(Path("data/raw"), Path("data/processed"))
