"""OA-12913 boarding/alighting collector and corridor builder.

Builds the Jongno-Myeongdong-Euljiro corridor datasets described in
data/README.md from the raw Seoul Open Data Plaza CSVs (OA-12913 and the
bus stop coordinate dataset).
"""

import calendar
import re
from pathlib import Path

import pandas as pd

from stationcast.ingest._common import clean_stop_name, is_night_bus, read_cp949_csv

# 데모 스코프: Jongno-Myeongdong-Euljiro corridor, 21 stops confirmed in
# data/README.md. build_* 함수들의 stop_ids=None은 필터 없음(서울 전체)을
# 뜻하고, 이 튜플은 scripts/build_processed.py가 STATIONCAST_SCOPE=demo일 때
# 명시적으로 넘기는 값이다.
DEMO_STOP_IDS: tuple[int, ...] = (
    100000385,
    100000386,
    100000387,
    100000388,
    100000389,
    100000390,
    100000391,
    100000392,
    101000021,
    101000027,
    101000032,
    101000040,
    101000041,
    101000042,
    101000043,
    101000057,
    101000059,
    101000060,
    101000061,
    101000114,
    101000141,
)

_HOUR_RE = re.compile(r"(\d+)시")

HOURLY_BOARDING_DIRNAME = "버스노선별_정류장별_시간대별_승하차_인원_정보"
"""Subdirectory of data/raw/ holding every OA-12913 monthly CSV (see
data/README.md §1) -- one recent year (2025-07~2026-06, 12 files) rather
than the single June 2026 snapshot used before, since one month's hourly
shape isn't representative of the corridor's real seasonal swings (school
term vs. summer break, holidays, etc.)."""


def load_boarding_alighting(csv_path: Path) -> pd.DataFrame:
    """Load one raw OA-12913 monthly CSV (cp949-encoded)."""
    return read_cp949_csv(csv_path, low_memory=False)


def load_stop_coordinates(csv_path: Path) -> pd.DataFrame:
    """Load the Seoul bus stop coordinate CSV (cp949-encoded)."""
    return read_cp949_csv(csv_path, low_memory=False)


def _days_in_month(year_month: int) -> int:
    """Number of days in a 사용년월 (YYYYMM) value, e.g. 202606 -> 30."""
    year, month = divmod(int(year_month), 100)
    return calendar.monthrange(year, month)[1]


def build_corridor_route_hourly(
    boarding_df: pd.DataFrame, stop_ids: tuple[int, ...] | None = None
) -> pd.DataFrame:
    """Aggregate to stop x route x hour daily-average boarding, keeping 노선번호.

    Keeps 노선번호 as its own grouping key (rather than summing across every
    route serving a stop) because estimator/wait_population.py pairs each
    route's own boarding with that route's own headway -- a passenger
    waiting for one route can't board a different route just because that
    one has empty seats.

    Only 승차 is kept -- the wait-population model has no use for 하차.
    stop_ids=None keeps every stop (서울 전체); pass DEMO_STOP_IDS for the
    21-stop demo corridor. Flags night-bus routes (N-접두, is_night_bus()) in
    their own column instead of excluding them -- their registered headway
    (corridor_route_schedule.parquet) flows into Little's Law like any other
    route's.

    boarding_df may be several months concatenated together (see run()),
    each with its own 사용년월 -- the raw hourly columns are that month's
    cumulative total for that hour-of-day (data/README.md section 1), so
    this sums every month's total per (stop, route, hour) and divides by
    the sum of each month's day count, i.e. the true daily average over
    the whole window rather than an average of monthly averages (which
    would silently over-weight short months).

    Grouped by 표준버스정류장ID alone, not also by 정류장명 (same reasoning
    as oa12912.py's build_corridor_daily): a stop's registered name can
    change mid-window (e.g. ID 101000042, 해운센터.롯데영플라자 ->
    소공동.롯데영플라자 on 2026-05-11), and grouping by name too would
    silently split one physical stop's boarding across two output rows for
    any hour where its name changed between the concatenated months. The
    most recent month's name is attached afterward as a single
    representative label.

    Melts the hourly columns into long form and does a single groupby
    rather than looping per hour-of-day and re-grouping the whole frame
    each time -- the loop cost used to be paid once per column (24x for a
    day-typed set of columns); melting first pays it once regardless of
    how many months or hour columns are concatenated together.
    """
    keep = boarding_df["표준버스정류장ID"].isin(stop_ids) if stop_ids is not None else None
    sub = boarding_df.copy() if keep is None else boarding_df[keep].copy()
    names = sub["역명"].unique()
    sub["정류장명"] = sub["역명"].map(
        dict(zip(names, map(clean_stop_name, names), strict=True))
    )
    sub["노선번호"] = sub["노선번호"].astype(str)
    sub["is_night_bus"] = sub["노선번호"].map(
        dict(zip(u := sub["노선번호"].unique(), map(is_night_bus, u), strict=True))
    )

    total_days = sum(_days_in_month(ym) for ym in boarding_df["사용년월"].unique())
    latest_name = sub.sort_values("사용년월").groupby("표준버스정류장ID")["정류장명"].last()

    on_cols = [c for c in boarding_df.columns if c.endswith("시승차총승객수")]
    melted = sub.melt(
        id_vars=["표준버스정류장ID", "노선번호", "is_night_bus"],
        value_vars=on_cols,
        var_name="_hour_col",
        value_name="승차",
    )
    hours = melted["_hour_col"].str.extract(_HOUR_RE, expand=False)
    assert hours.notna().all(), f"unexpected hour column name(s): {on_cols}"
    melted["시간대"] = hours.astype(int)

    result = (
        melted.groupby(["표준버스정류장ID", "노선번호", "is_night_bus", "시간대"])
        .agg(승차=("승차", "sum"))
        .reset_index()
    )
    result["승차"] = result["승차"] / total_days
    result = result.merge(latest_name, on="표준버스정류장ID", how="left")

    return (
        result[["표준버스정류장ID", "정류장명", "노선번호", "is_night_bus", "시간대", "승차"]]
        .sort_values(["표준버스정류장ID", "노선번호", "시간대"])
        .reset_index(drop=True)
    )


def build_corridor_stops(
    boarding_df: pd.DataFrame,
    coord_df: pd.DataFrame,
    stop_ids: tuple[int, ...] | None = None,
) -> pd.DataFrame:
    """Build per-stop metadata (name, ARS number, coordinates) for the corridor.

    stop_ids=None keeps every stop (서울 전체); pass DEMO_STOP_IDS for the
    21-stop demo corridor.
    """
    keep = boarding_df["표준버스정류장ID"].isin(stop_ids) if stop_ids is not None else None
    sub = boarding_df.copy() if keep is None else boarding_df[keep].copy()
    names = sub["역명"].unique()
    sub["정류장명"] = sub["역명"].map(
        dict(zip(names, map(clean_stop_name, names), strict=True))
    )
    meta = sub[["표준버스정류장ID", "정류장명", "버스정류장ARS번호"]].drop_duplicates(
        subset="표준버스정류장ID"
    )
    meta = meta.rename(columns={"버스정류장ARS번호": "ARS번호"})

    coords = coord_df[["정류소번호", "X좌표", "Y좌표", "정류소 타입"]].drop_duplicates(
        subset="정류소번호"
    )
    result = meta.merge(coords, left_on="표준버스정류장ID", right_on="정류소번호", how="left")
    return (
        result.drop(columns=["정류소번호"]).sort_values("표준버스정류장ID").reset_index(drop=True)
    )


def run(raw_dir: Path, out_dir: Path, stop_ids: tuple[int, ...] | None = DEMO_STOP_IDS) -> None:
    """Build corridor_route_hourly.parquet and corridor_stops.parquet from raw_dir CSVs.

    corridor_route_hourly averages over every OA-12913 monthly CSV found
    under raw_dir/HOURLY_BOARDING_DIRNAME. corridor_stops only needs one
    month for its per-stop metadata (name/ARS/coordinates), so it uses the
    most recent file rather than paying to scan all of them.

    stop_ids defaults to the 21-stop demo corridor; pass None for 서울 전체
    (scripts/build_processed.py does this when STATIONCAST_SCOPE=seoul).
    """
    hourly_dir = raw_dir / HOURLY_BOARDING_DIRNAME
    hourly_csvs = sorted(hourly_dir.glob("*버스노선별_정류장별_시간대별_승하차*.csv"))
    if not hourly_csvs:
        raise FileNotFoundError(f"No OA-12913 monthly CSVs found in {hourly_dir}")
    coord_csv = next(raw_dir.glob("*버스정류소*위치정보*.csv"))

    monthly_frames = [load_boarding_alighting(p) for p in hourly_csvs]
    boarding_df = pd.concat(monthly_frames, ignore_index=True)
    coord_df = load_stop_coordinates(coord_csv)

    route_hourly = build_corridor_route_hourly(boarding_df, stop_ids=stop_ids)
    stops = build_corridor_stops(monthly_frames[-1], coord_df, stop_ids=stop_ids)

    out_dir.mkdir(parents=True, exist_ok=True)
    route_hourly.to_parquet(out_dir / "corridor_route_hourly.parquet", index=False)
    stops.to_parquet(out_dir / "corridor_stops.parquet", index=False)


if __name__ == "__main__":
    run(Path("data/raw"), Path("data/processed"))
