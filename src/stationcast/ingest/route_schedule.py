"""Seoul bus route schedule collector.

Prepares the input data for issue #51 (capacity constraint): joins each
corridor stop's serving routes (already derivable from OA-12913, see
oa12913.py) with that route's headway and fleet size
(서울시버스노선기본정보).
"""

from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from stationcast.ingest._common import clean_stop_name, is_night_bus, read_cp949_csv
from stationcast.ingest.oa12913 import DEMO_STOP_IDS, HOURLY_BOARDING_DIRNAME

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
    stop_ids: tuple[int, ...] | None = None,
) -> pd.DataFrame:
    """Join each corridor stop's serving routes with their day-type schedule.

    Route-stop membership already exists in OA-12913 (§1 데이터셋①) -- no
    separate stop-sequence file is needed; a route serving a stop shows up
    there regardless of headway data availability. stop_ids=None keeps
    every stop (서울 전체); pass DEMO_STOP_IDS for the 21-stop demo corridor.

    route_schedule rows are deduplicated by (노선번호, 요일유형) before
    joining: a route run jointly by multiple companies (공동배차) appears
    once per participating company with identical 배차간격/인가대수, and
    joining without deduplication would multiply a stop's effective route
    count by however many companies share that route.

    Routes with no matching schedule row, or a 배차간격 of 0 (e.g. newly
    registered routes without a published schedule yet), are flagged via
    배차정보없음 rather than dropped, so gaps stay visible downstream
    instead of silently disappearing.

    Flags night-bus routes (N-접두, is_night_bus()) in their own column
    instead of excluding them (see oa12913.py's build_corridor_route_hourly)
    -- their 25~140분 registered headway range is real schedule data, not
    noise, and estimator/wait_population.py's cv_r already generalizes to
    whatever range a route's 최소배차/최대배차 reports.

    Crossed against every 요일유형 before joining schedule data (rather than
    joining on 노선번호 alone) so a route with *no* matching row in any
    sheet -- plausible for night buses, which may not appear in
    서울시버스노선기본정보 at all -- still gets one row per day type with
    배차정보없음=True, instead of collapsing to a single day-type-less row.
    """
    keep = boarding_df["표준버스정류장ID"].isin(stop_ids) if stop_ids is not None else None
    sub = boarding_df.copy() if keep is None else boarding_df[keep].copy()
    sub["정류장명"] = sub["역명"].apply(clean_stop_name)
    sub["노선번호"] = sub["노선번호"].astype(str)
    corridor_routes = sub[["표준버스정류장ID", "정류장명", "노선번호"]].drop_duplicates()
    corridor_routes["is_night_bus"] = corridor_routes["노선번호"].map(
        dict(zip(u := corridor_routes["노선번호"].unique(), map(is_night_bus, u), strict=True))
    )

    day_types = pd.DataFrame({"요일유형": list(_SHEET_TO_DAY_TYPE.values())})
    corridor_route_days = corridor_routes.merge(day_types, how="cross")

    schedule_dedup = route_schedule.drop_duplicates(subset=["노선번호", "요일유형"])
    result = corridor_route_days.merge(schedule_dedup, on=["노선번호", "요일유형"], how="left")
    result["배차정보없음"] = result["배차간격"].isna() | (result["배차간격"] == 0)

    return (
        result[
            [
                "표준버스정류장ID",
                "정류장명",
                "노선번호",
                "is_night_bus",
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

    Raises ValueError if a stop has *no* route with a value in some column
    (issue #109): the median itself is then undefined (NaN), and letting
    that NaN flow through would silently turn into a NaN W or capacity
    figure downstream instead of a visible failure.
    """
    merged = merged.copy()
    for col in columns:
        merged[col] = merged[col].fillna(merged.groupby(group_col)[col].transform("median"))

    still_missing = merged[merged[list(columns)].isna().any(axis=1)]
    if not still_missing.empty:
        stop_ids = sorted(int(s) for s in still_missing[group_col].unique())
        raise ValueError(
            f"no schedule data for any route at stop(s) {stop_ids} in columns "
            f"{list(columns)} -- median fallback has nothing to fall back to"
        )
    return merged


def run(
    raw_dir: Path, out_dir: Path, stop_ids: tuple[int, ...] | None = DEMO_STOP_IDS
) -> None:
    """Build corridor_route_schedule.parquet from raw_dir CSV/XLSX.

    Route-stop membership only needs one month's OA-12913 file (routes
    don't come and go month to month), so this uses the most recent one
    under raw_dir/HOURLY_BOARDING_DIRNAME rather than reading all of them.

    stop_ids defaults to the 21-stop demo corridor; pass None for 서울 전체
    (scripts/build_processed.py does this when STATIONCAST_SCOPE=seoul).
    """
    boarding_csv = sorted(
        (raw_dir / HOURLY_BOARDING_DIRNAME).glob("*버스노선별_정류장별_시간대별_승하차*.csv")
    )[-1]
    schedule_xlsx = next(raw_dir.glob("*버스노선기본정보*.xlsx"))

    boarding_df = read_cp949_csv(boarding_csv, low_memory=False)
    route_schedule = load_route_schedule(schedule_xlsx)

    schedule = build_corridor_route_schedule(boarding_df, route_schedule, stop_ids=stop_ids)

    out_dir.mkdir(parents=True, exist_ok=True)
    schedule.to_parquet(out_dir / "corridor_route_schedule.parquet", index=False)


if __name__ == "__main__":
    run(Path("data/raw"), Path("data/processed"))
