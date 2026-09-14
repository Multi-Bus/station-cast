"""OA-12912 daily boarding/alighting collector.

Complements oa12913.py (hourly, monthly-aggregated) with per-date
granularity for the same Jongno-Myeongdong-Euljiro corridor. Used by
features/ (issue #10) to derive weekday/weekend/holiday/seasonal
correction factors, since OA-12913 alone has no per-date breakdown.
"""

from pathlib import Path

import pandas as pd

from stationcast.ingest._common import clean_stop_name, read_cp949_csv
from stationcast.ingest.oa12913 import DEMO_STOP_IDS


def load_daily_boarding(csv_path: Path) -> pd.DataFrame:
    """Load one month's raw OA-12912 CSV (cp949-encoded)."""
    return read_cp949_csv(csv_path, low_memory=False)


def build_corridor_daily(
    boarding_df: pd.DataFrame, stop_ids: tuple[int, ...] | None = None
) -> pd.DataFrame:
    """Aggregate route-level daily rows into stop x date boarding/alighting totals.

    Sums across every route serving a stop (night buses included -- see
    oa12913.py's build_corridor_route_hourly): this dataset only feeds
    features/ (issue #10)'s weekday/weekend/holiday correction factors,
    which are stop-scoped, not route-scoped. ``boarding_df`` may span
    multiple months concatenated together (see run()). stop_ids=None keeps
    every stop (서울 전체); pass DEMO_STOP_IDS for the 21-stop demo corridor.

    Grouped by 표준버스정류장ID alone (not also by name): a stop's
    registered name can change mid-period (e.g., ID 101000042 was renamed
    from 해운센터.롯데영플라자 to 소공동.롯데영플라자 on 2026-05-11 within
    the 12-month history), and grouping by name too would split one
    physical stop's continuous series into two. The most recent name is
    attached afterward as a single representative label.

    표준버스정류장ID is coerced to numeric before filtering: some monthly
    CSVs (e.g. 202312, 202401) have a single row using '~' as a
    virtual/depot-stop placeholder (the same convention documented for
    ARS번호), which makes pandas infer that whole column as string dtype
    for that file. Without coercion, an int-based .isin() silently matches
    nothing and drops the entire month.
    """
    stop_id_num = pd.to_numeric(boarding_df["표준버스정류장ID"], errors="coerce")
    keep = stop_id_num.notna() if stop_ids is None else stop_id_num.isin(stop_ids)
    sub = boarding_df[keep].copy()
    sub["표준버스정류장ID"] = stop_id_num[keep].astype("int64")
    names = sub["역명"].unique()
    sub["정류장명"] = sub["역명"].map(
        dict(zip(names, map(clean_stop_name, names), strict=True))
    )

    daily_totals = (
        sub.groupby(["표준버스정류장ID", "사용일자"])
        .agg(승차=("승차총승객수", "sum"), 하차=("하차총승객수", "sum"))
        .reset_index()
    )
    latest_name = sub.sort_values("사용일자").groupby("표준버스정류장ID")["정류장명"].last()
    result = daily_totals.merge(latest_name, on="표준버스정류장ID", how="left")

    return (
        result[["표준버스정류장ID", "정류장명", "사용일자", "승차", "하차"]]
        .sort_values(["표준버스정류장ID", "사용일자"])
        .reset_index(drop=True)
    )


def run(
    raw_dir: Path, out_dir: Path, stop_ids: tuple[int, ...] | None = DEMO_STOP_IDS
) -> None:
    """Build corridor_daily.parquet from every OA-12912 monthly CSV in raw_dir.

    Picks up all files matching ``BUS_STATION_BOARDING_MONTH_*.csv`` so
    additional months can be dropped into raw_dir and reprocessed without
    code changes. stop_ids defaults to the 21-stop demo corridor; pass None
    for 서울 전체 (scripts/build_processed.py does this when
    STATIONCAST_SCOPE=seoul).
    """
    csv_paths = sorted(raw_dir.glob("BUS_STATION_BOARDING_MONTH_*.csv"))
    if not csv_paths:
        raise FileNotFoundError(f"No OA-12912 monthly CSVs found in {raw_dir}")

    monthly_frames = [load_daily_boarding(p) for p in csv_paths]
    combined = pd.concat(monthly_frames, ignore_index=True)
    daily = build_corridor_daily(combined, stop_ids=stop_ids)

    out_dir.mkdir(parents=True, exist_ok=True)
    daily.to_parquet(out_dir / "corridor_daily.parquet", index=False)


if __name__ == "__main__":
    run(Path("data/raw"), Path("data/processed"))
