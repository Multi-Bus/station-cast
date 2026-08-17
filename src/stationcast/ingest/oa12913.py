"""OA-12913 boarding/alighting collector and corridor builder.

Builds the Jongno-Myeongdong-Euljiro corridor datasets described in
data/README.md from the raw Seoul Open Data Plaza CSVs (OA-12913 and the
bus stop coordinate dataset).
"""

import calendar
import re
from pathlib import Path

import pandas as pd

# Jongno-Myeongdong-Euljiro corridor: 21 stops confirmed in data/README.md
CORRIDOR_STOP_IDS: tuple[int, ...] = (
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

# 서울심야버스(N-접두) 노선: 회랑 21개 정류장에 걸리는 10개 노선. 자정 이후에만
# 운행하고 배차간격도 25~140분으로 일반 노선과 특성이 달라 모델 스코프에서
# 제외한다. OA-12912·route_schedule.py 등 교통수단타입명 컬럼이 없는
# 데이터셋에서도 동일하게 걸러낼 수 있도록 노선번호로 명시한다.
CORRIDOR_NIGHT_BUS_ROUTES: tuple[str, ...] = (
    "N15",
    "N16",
    "N26",
    "N30",
    "N31",
    "N37",
    "N51",
    "N62",
    "N73",
    "N75",
)

_NAME_SUFFIX_RE = re.compile(r"\(\d+\)$")
_HOUR_RE = re.compile(r"(\d+)시")


def _clean_stop_name(name: object) -> str:
    """Strip the trailing per-route sequence number from a raw 역명 value."""
    return _NAME_SUFFIX_RE.sub("", str(name))


def load_boarding_alighting(csv_path: Path) -> pd.DataFrame:
    """Load the raw OA-12913 monthly CSV (cp949-encoded)."""
    return pd.read_csv(csv_path, encoding="cp949", low_memory=False)


def load_stop_coordinates(csv_path: Path) -> pd.DataFrame:
    """Load the Seoul bus stop coordinate CSV (cp949-encoded)."""
    return pd.read_csv(csv_path, encoding="cp949", low_memory=False)


def _days_in_month(year_month: int) -> int:
    """Number of days in a 사용년월 (YYYYMM) value, e.g. 202606 -> 30."""
    year, month = divmod(int(year_month), 100)
    return calendar.monthrange(year, month)[1]


def build_corridor_route_hourly(
    boarding_df: pd.DataFrame, stop_ids: tuple[int, ...] = CORRIDOR_STOP_IDS
) -> pd.DataFrame:
    """Aggregate to stop x route x hour daily-average boarding, keeping 노선번호.

    Keeps 노선번호 as its own grouping key (rather than summing across every
    route serving a stop) because estimator/wait_population.py pairs each
    route's own boarding with that route's own headway -- a passenger
    waiting for one route can't board a different route just because that
    one has empty seats.

    Only 승차 is kept -- the wait-population model has no use for 하차.
    Excludes CORRIDOR_NIGHT_BUS_ROUTES (see CORRIDOR_NIGHT_BUS_ROUTES's own
    docstring). The raw hourly columns are a full month's cumulative total
    for that hour-of-day (data/README.md section 1); dividing by the month's
    day count here turns that into the daily average the model needs.
    """
    sub = boarding_df[boarding_df["표준버스정류장ID"].isin(stop_ids)].copy()
    sub = sub[~sub["노선번호"].astype(str).isin(CORRIDOR_NIGHT_BUS_ROUTES)]
    sub["정류장명"] = sub["역명"].apply(_clean_stop_name)
    sub["노선번호"] = sub["노선번호"].astype(str)

    days = _days_in_month(boarding_df["사용년월"].iloc[0])

    on_cols = [c for c in boarding_df.columns if c.endswith("시승차총승객수")]

    frames = []
    for on_col in on_cols:
        match = _HOUR_RE.match(on_col)
        assert match is not None, f"unexpected hour column name: {on_col}"
        hour = int(match.group(1))
        grp = (
            sub.groupby(["표준버스정류장ID", "정류장명", "노선번호"])
            .agg(승차=(on_col, "sum"))
            .reset_index()
        )
        grp["승차"] = grp["승차"] / days
        grp["시간대"] = hour
        frames.append(grp)

    result = pd.concat(frames, ignore_index=True)
    return (
        result[["표준버스정류장ID", "정류장명", "노선번호", "시간대", "승차"]]
        .sort_values(["표준버스정류장ID", "노선번호", "시간대"])
        .reset_index(drop=True)
    )


def build_corridor_stops(
    boarding_df: pd.DataFrame,
    coord_df: pd.DataFrame,
    stop_ids: tuple[int, ...] = CORRIDOR_STOP_IDS,
) -> pd.DataFrame:
    """Build per-stop metadata (name, ARS number, coordinates) for the corridor."""
    sub = boarding_df[boarding_df["표준버스정류장ID"].isin(stop_ids)].copy()
    sub["정류장명"] = sub["역명"].apply(_clean_stop_name)
    meta = sub[["표준버스정류장ID", "정류장명", "버스정류장ARS번호"]].drop_duplicates(
        subset="표준버스정류장ID"
    )
    meta = meta.rename(columns={"버스정류장ARS번호": "ARS번호"})

    coords = coord_df[["정류소번호", "X좌표", "Y좌표", "정류소 타입"]].drop_duplicates(
        subset="정류소번호"
    )
    result = meta.merge(coords, left_on="표준버스정류장ID", right_on="정류소번호", how="left")
    return (
        result.drop(columns=["정류소번호"])
        .sort_values("표준버스정류장ID")
        .reset_index(drop=True)
    )


def run(raw_dir: Path, out_dir: Path) -> None:
    """Build corridor_hourly.parquet and corridor_stops.parquet from raw_dir CSVs."""
    boarding_csv = next(raw_dir.glob("*버스노선별_정류장별_시간대별_승하차*.csv"))
    coord_csv = next(raw_dir.glob("*버스정류소*위치정보*.csv"))

    boarding_df = load_boarding_alighting(boarding_csv)
    coord_df = load_stop_coordinates(coord_csv)

    route_hourly = build_corridor_route_hourly(boarding_df)
    stops = build_corridor_stops(boarding_df, coord_df)

    out_dir.mkdir(parents=True, exist_ok=True)
    route_hourly.to_parquet(out_dir / "corridor_route_hourly.parquet", index=False)
    stops.to_parquet(out_dir / "corridor_stops.parquet", index=False)


if __name__ == "__main__":
    run(Path("data/raw"), Path("data/processed"))
