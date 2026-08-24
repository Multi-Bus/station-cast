"""Seoul bus route schedule collector.

Prepares the input data for issue #51 (capacity constraint): joins each
corridor stop's serving routes (already derivable from OA-12913, see
oa12913.py) with that route's headway and fleet size
(서울시버스노선기본정보).
"""

from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from stationcast.ingest._common import clean_stop_name, read_cp949_csv
from stationcast.ingest.oa12913 import CORRIDOR_NIGHT_BUS_ROUTES, CORRIDOR_STOP_IDS

_SHEET_TO_DAY_TYPE = {
    "평일공동배차": "평일",
    "토요일공동배차": "토요일",
    "공휴일공동배차": "공휴일",
}

_SCHEDULE_COLUMNS = ["노선번호", "요일유형", "배차간격", "인가대수", "최소배차", "최대배차"]


def load_route_schedule(xlsx_path: Path) -> pd.DataFrame:
    """Load headway/fleet-size data for every route, tagged by day type.

    One row per (route, participating company) as stored in the source
    file: routes run jointly by multiple companies (공동배차) appear once
    per company with identical 배차간격/인가대수. Deduplication happens
    in build_corridor_route_schedule, not here.
    """
    sheets = pd.read_excel(xlsx_path, sheet_name=None)
    frames = []
    for sheet_name, day_type in _SHEET_TO_DAY_TYPE.items():
        sheet = sheets[sheet_name].copy()
        sheet["노선번호"] = sheet["노선번호"].astype(str)
        sheet["요일유형"] = day_type
        frames.append(sheet[_SCHEDULE_COLUMNS])
    return pd.concat(frames, ignore_index=True)


def build_corridor_route_schedule(
    boarding_df: pd.DataFrame,
    route_schedule: pd.DataFrame,
    stop_ids: tuple[int, ...] = CORRIDOR_STOP_IDS,
) -> pd.DataFrame:
    """Join each corridor stop's serving routes with their day-type schedule.

    Route-stop membership already exists in OA-12913 (§1 데이터셋①) -- no
    separate stop-sequence file is needed; a route serving a stop shows up
    there regardless of headway data availability.

    route_schedule rows are deduplicated by (노선번호, 요일유형) before
    joining: a route run jointly by multiple companies (공동배차) appears
    once per participating company with identical 배차간격/인가대수, and
    joining without deduplication would multiply a stop's effective route
    count by however many companies share that route.

    Routes with no matching schedule row, or a 배차간격 of 0 (e.g. newly
    registered routes without a published schedule yet), are flagged via
    배차정보없음 rather than dropped, so gaps stay visible downstream
    instead of silently disappearing.

    Excludes CORRIDOR_NIGHT_BUS_ROUTES (same exclusion as
    build_corridor_route_hourly in oa12913.py).
    """
    sub = boarding_df[boarding_df["표준버스정류장ID"].isin(stop_ids)].copy()
    sub = sub[~sub["노선번호"].astype(str).isin(CORRIDOR_NIGHT_BUS_ROUTES)]
    sub["정류장명"] = sub["역명"].apply(clean_stop_name)
    sub["노선번호"] = sub["노선번호"].astype(str)
    corridor_routes = sub[["표준버스정류장ID", "정류장명", "노선번호"]].drop_duplicates()

    schedule_dedup = route_schedule.drop_duplicates(subset=["노선번호", "요일유형"])
    result = corridor_routes.merge(schedule_dedup, on="노선번호", how="left")
    result["배차정보없음"] = result["배차간격"].isna() | (result["배차간격"] == 0)

    return (
        result[
            [
                "표준버스정류장ID",
                "정류장명",
                "노선번호",
                "요일유형",
                "배차간격",
                "인가대수",
                "최소배차",
                "최대배차",
                "배차정보없음",
            ]
        ]
        .sort_values(["표준버스정류장ID", "요일유형", "노선번호"])
        .reset_index(drop=True)
    )


def fill_missing_headway(
    merged: pd.DataFrame, columns: Sequence[str], group_col: str = "표준버스정류장ID"
) -> pd.DataFrame:
    """Fill missing headway-derived columns with the same stop's other routes' median.

    ``merged`` is route_hourly (or route_hourly x route_schedule for a
    capacity check) left-joined against corridor_route_schedule -- rows with
    no matching schedule, or flagged 배차정보없음 and pre-filtered out before
    the join, land here with NaN in ``columns`` (e.g. 배차간격, 최소배차,
    최대배차). A single route missing schedule data shouldn't zero out or
    drop that route's real boarding count, so it borrows the median of the
    *other* routes serving the same stop that hour instead.

    Shared by estimator/wait_population.py's W(s,t) calculation and
    validate/physical_constraints.py's capacity check, which used to
    reimplement this fallback separately -- letting the two silently drift
    apart was the risk (each module's own tests would still pass even if the
    fallback diverged, since neither compares against the other).

    A stop with no route carrying a value in some column falls back to NaN
    (median of an all-missing group) -- issue #109 covers guarding that case
    explicitly instead of letting it flow through silently.
    """
    merged = merged.copy()
    for col in columns:
        merged[col] = merged[col].fillna(merged.groupby(group_col)[col].transform("median"))
    return merged


def run(raw_dir: Path, out_dir: Path) -> None:
    """Build corridor_route_schedule.parquet from raw_dir CSV/XLSX."""
    boarding_csv = next(raw_dir.glob("*버스노선별_정류장별_시간대별_승하차*.csv"))
    schedule_xlsx = next(raw_dir.glob("*버스노선기본정보*.xlsx"))

    boarding_df = read_cp949_csv(boarding_csv, low_memory=False)
    route_schedule = load_route_schedule(schedule_xlsx)

    schedule = build_corridor_route_schedule(boarding_df, route_schedule)

    out_dir.mkdir(parents=True, exist_ok=True)
    schedule.to_parquet(out_dir / "corridor_route_schedule.parquet", index=False)


if __name__ == "__main__":
    run(Path("data/raw"), Path("data/processed"))
