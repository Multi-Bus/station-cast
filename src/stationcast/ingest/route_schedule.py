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

_SCHEDULE_COLUMNS = ["노선번호", "유형", "요일유형", "배차간격", "인가대수", "최소배차", "최대배차"]


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

    # Deduplicate on (정류장, 노선) alone and attach the most recent name
    # afterwards, the same way oa12913.py and oa12912.py do. Keeping 정류장명
    # in the key splits a renamed stop into one row per name -- 814 of 서울
    # 전체's 12,595 stops were renamed across the 12-month window (11 of them
    # twice) -- and estimator/wait_population.py joins on (정류장, 노선) only,
    # so each extra row duplicated that stop's boarding and multiplied its W.
    latest_name = sub.sort_values("사용년월").groupby("표준버스정류장ID")["정류장명"].last()
    corridor_routes = sub[["표준버스정류장ID", "노선번호"]].drop_duplicates()
    corridor_routes = corridor_routes.merge(latest_name, on="표준버스정류장ID", how="left")
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
                "유형",
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


def day_type_schedule(
    route_schedule: pd.DataFrame, day_type: str, columns: Sequence[str]
) -> pd.DataFrame:
    """One day type's per-(stop, route) headway columns, ready to left-join.

    Rows flagged 배차정보없음 keep their place with NaN in ``columns``
    rather than being dropped: the join would produce the same NaN either
    way, but keeping the row carries 유형 along, which is what
    fill_missing_headway()'s second fallback level needs. Shared by
    estimator/wait_population.py and validate/physical_constraints.py so
    the two can't drift apart in how they prepare the same join.
    """
    schedule = route_schedule[route_schedule["요일유형"] == day_type].copy()
    schedule.loc[schedule["배차정보없음"], list(columns)] = pd.NA
    return schedule[["표준버스정류장ID", "노선번호", "유형", *columns]]


def fill_missing_headway(
    merged: pd.DataFrame,
    columns: Sequence[str],
    group_col: str = "표준버스정류장ID",
    type_col: str = "유형",
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

    A stop whose routes *all* lack schedule data has no sibling to borrow
    from -- impossible in the 21-stop demo corridor (every stop is a
    downtown arterial with several routes), but 125 of 서울 전체's 12,595
    stops hit it, 117 of them served by a single route. Those fall back a
    second level, to the median of every 서울 route of the same 유형.
    유형 is what actually separates headways -- 간선 11분, 지선 12분, 마을
    13분, 광역 15분, but 공항 50분 and 한강 75분 -- so a single citywide
    median would understate a 한강버스 stop's wait about sixfold. Medians
    come from one row per 노선번호, so a route serving many stops doesn't
    outvote the rest of its 유형, and from the pre-fill values, so the
    first level's substitutions don't feed the second.

    Rows whose 유형 is itself unknown are dropped: the route is absent from
    서울시버스노선기본정보 altogether (8 routes, data/README.md §10), so
    there is no group to borrow from and nothing to compute W from. Raises
    ValueError if anything is still missing after both levels (issue #109)
    -- a known 유형 with no schedule data anywhere in 서울 is a real
    failure, not a data gap, and letting the NaN through would surface
    downstream as a NaN W or capacity figure instead.
    """
    merged = merged.copy()
    per_route = merged.drop_duplicates(subset=["노선번호"])
    for col in columns:
        type_median = per_route.groupby(type_col)[col].median()
        merged[col] = merged[col].fillna(merged.groupby(group_col)[col].transform("median"))
        merged[col] = merged[col].fillna(merged[type_col].map(type_median))

    unresolved = merged[list(columns)].isna().any(axis=1)
    merged = merged[~(unresolved & merged[type_col].isna())]

    still_missing = merged[merged[list(columns)].isna().any(axis=1)]
    if not still_missing.empty:
        stop_ids = sorted(int(s) for s in still_missing[group_col].unique())
        raise ValueError(
            f"no schedule data for any route at stop(s) {stop_ids} in columns "
            f"{list(columns)} -- median fallback has nothing to fall back to"
        )
    return merged.reset_index(drop=True)


def run(
    raw_dir: Path, out_dir: Path, stop_ids: tuple[int, ...] | None = DEMO_STOP_IDS
) -> None:
    """Build corridor_route_schedule.parquet from raw_dir CSV/XLSX.

    Reads every monthly OA-12913 file under raw_dir/HOURLY_BOARDING_DIRNAME,
    the same set oa12913.py's build_corridor_route_hourly() aggregates, so
    the two outputs agree on which routes serve which stops. This used to
    read only the most recent month on the assumption that routes don't come
    and go month to month; over 12 months of 서울 전체 they do -- seasonal
    routes, 출퇴근 전용 variants, and renumbered routes left 392 (stop,
    route) pairs present in corridor_route_hourly with no row here at all.
    Those pairs joined to nothing downstream, taking 58 stops out of
    corridor_wait entirely (estimator/wait_population.py).

    stop_ids defaults to the 21-stop demo corridor; pass None for 서울 전체
    (scripts/build_processed.py does this when STATIONCAST_SCOPE=seoul).
    """
    boarding_csvs = sorted(
        (raw_dir / HOURLY_BOARDING_DIRNAME).glob("*버스노선별_정류장별_시간대별_승하차*.csv")
    )
    schedule_xlsx = next(raw_dir.glob("*버스노선기본정보*.xlsx"))

    boarding_df = pd.concat(
        [read_cp949_csv(path, low_memory=False) for path in boarding_csvs], ignore_index=True
    )
    route_schedule = load_route_schedule(schedule_xlsx)

    schedule = build_corridor_route_schedule(boarding_df, route_schedule, stop_ids=stop_ids)

    out_dir.mkdir(parents=True, exist_ok=True)
    schedule.to_parquet(out_dir / "corridor_route_schedule.parquet", index=False)


if __name__ == "__main__":
    run(Path("data/raw"), Path("data/processed"))
