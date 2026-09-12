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


def load_boarding_alighting(csv_path: Path) -> pd.DataFrame:
    """Load the raw OA-12913 monthly CSV (cp949-encoded)."""
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
    (25~140분, corridor_route_schedule.parquet) flows into Little's Law like
    any other route's. The raw hourly columns are a full month's cumulative
    total for that hour-of-day (data/README.md section 1); dividing by the
    month's day count here turns that into the daily average the model needs.
    """
    keep = boarding_df["표준버스정류장ID"].isin(stop_ids) if stop_ids is not None else None
    sub = boarding_df.copy() if keep is None else boarding_df[keep].copy()
    sub["정류장명"] = sub["역명"].apply(clean_stop_name)
    sub["노선번호"] = sub["노선번호"].astype(str)
    sub["is_night_bus"] = sub["노선번호"].map(
        dict(zip(u := sub["노선번호"].unique(), map(is_night_bus, u), strict=True))
    )

    days = _days_in_month(boarding_df["사용년월"].iloc[0])

    on_cols = [c for c in boarding_df.columns if c.endswith("시승차총승객수")]

    frames = []
    for on_col in on_cols:
        match = _HOUR_RE.match(on_col)
        assert match is not None, f"unexpected hour column name: {on_col}"
        hour = int(match.group(1))
        grp = (
            sub.groupby(["표준버스정류장ID", "정류장명", "노선번호", "is_night_bus"])
            .agg(승차=(on_col, "sum"))
            .reset_index()
        )
        grp["승차"] = grp["승차"] / days
        grp["시간대"] = hour
        frames.append(grp)

    result = pd.concat(frames, ignore_index=True)
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
    sub["정류장명"] = sub["역명"].apply(clean_stop_name)
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

    stop_ids defaults to the 21-stop demo corridor; pass None for 서울 전체
    (scripts/build_processed.py does this when STATIONCAST_SCOPE=seoul).
    """
    boarding_csv = next(raw_dir.glob("*버스노선별_정류장별_시간대별_승하차*.csv"))
    coord_csv = next(raw_dir.glob("*버스정류소*위치정보*.csv"))

    boarding_df = load_boarding_alighting(boarding_csv)
    coord_df = load_stop_coordinates(coord_csv)

    route_hourly = build_corridor_route_hourly(boarding_df, stop_ids=stop_ids)
    stops = build_corridor_stops(boarding_df, coord_df, stop_ids=stop_ids)

    out_dir.mkdir(parents=True, exist_ok=True)
    route_hourly.to_parquet(out_dir / "corridor_route_hourly.parquet", index=False)
    stops.to_parquet(out_dir / "corridor_stops.parquet", index=False)


if __name__ == "__main__":
    run(Path("data/raw"), Path("data/processed"))
