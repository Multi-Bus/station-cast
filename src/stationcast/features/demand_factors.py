"""Weekday/holiday/weather/temperature demand correction factors (issue #10).

Joins corridor_daily.parquet (per-stop daily boarding/alighting, from
ingest/oa12912.py) with weather_daily.parquet and holiday_daily.parquet
on 사용일자, labels each date 평일 or 주말+공휴일 (weekends are computed
directly from the date; holidays come from holiday_daily.parquet), 강수
or 맑음, and a 저온/보통/고온 temperature tercile, and derives per-stop
correction factors from those labels.
"""

from pathlib import Path

import pandas as pd

_WEEKEND_DAYOFWEEK = {5, 6}  # Saturday, Sunday (pandas dayofweek: Monday=0)

# Correction factors outside this range are flagged for manual review
# rather than silently trusted (agreed post-hoc outlier check).
_OUTLIER_LOW = 0.5
_OUTLIER_HIGH = 2.0

_TEMP_LABELS = ["저온", "보통", "고온"]

# 보정계수의 기준선 그룹: 표본이 가장 크고 "평소"에 해당하는 조합.
_BASELINE_GROUP = ("평일", "맑음", "보통")

# 최고기온 3분위 경계값(3년치 데이터의 qcut 결과를 고정 상수로 전환).
_TEMP_BOUNDARIES = (13.9, 25.9)


def _day_type(dates: pd.Series, holiday_dates: set[int]) -> pd.Series:
    """Label each 사용일자 as 평일 or 주말+공휴일."""
    dow = pd.to_datetime(dates, format="%Y%m%d").dt.dayofweek
    is_weekend = dow.isin(_WEEKEND_DAYOFWEEK)
    is_holiday = dates.isin(holiday_dates)
    is_non_weekday = is_weekend | is_holiday
    return is_non_weekday.map({True: "주말+공휴일", False: "평일"})


def _weather_type(precipitation: pd.Series, snowfall: pd.Series) -> pd.Series:
    """Label each day 강수 or 맑음 (강수량>0 또는 신적설>0 이면 강수)."""
    has_precip = (precipitation > 0) | (snowfall > 0)
    return has_precip.map({True: "강수", False: "맑음"})


def classify_temperature(high_temp: float) -> str:
    """Label one day's 최고기온 저온/보통/고온 (single-value counterpart to _temp_type())."""
    low, high = _TEMP_BOUNDARIES
    if high_temp <= low:
        return _TEMP_LABELS[0]
    if high_temp <= high:
        return _TEMP_LABELS[1]
    return _TEMP_LABELS[2]


def _temp_type(high_temps: pd.Series) -> pd.Series:
    """Label each day 저온/보통/고온 by fixed 최고기온 boundaries (most correlated
    with ridership among the weather columns -- see issue discussion)."""
    return pd.cut(
        high_temps,
        bins=[-float("inf"), *_TEMP_BOUNDARIES, float("inf")],
        labels=_TEMP_LABELS,
    )


def build_features_daily(
    corridor_daily: pd.DataFrame,
    weather_daily: pd.DataFrame,
    holiday_daily: pd.DataFrame,
) -> pd.DataFrame:
    """Join corridor/weather/holiday data and attach 요일구분/날씨구분/기온구분 labels."""
    holiday_dates = set(holiday_daily["사용일자"])
    merged = corridor_daily.merge(weather_daily, on="사용일자", how="left")
    merged["요일구분"] = _day_type(merged["사용일자"], holiday_dates)
    merged["날씨구분"] = _weather_type(merged["강수량"], merged["신적설"])
    merged["기온구분"] = _temp_type(merged["최고기온"])
    return merged


def factor_column_name(value: str, day_type: str, weather_type: str, temp_type: str) -> str:
    """Build a 요일구분×날씨구분×기온구분 wide-format column name (issue #105).

    e.g. factor_column_name("보정계수_승차", "평일", "맑음", "보통")
    -> "보정계수_승차_평일_맑음_보통". Single source for this naming convention:
    api/main.py's lookup and validate/boarding_reproduction.py's parser both
    need to agree with whatever this module generates.
    """
    return f"{value}_{day_type}_{weather_type}_{temp_type}"


def classify_day_type(date: int, holiday_dates: set[int]) -> str:
    """Classify a date as 공휴일 > 주말 > 평일 (holiday takes priority over weekend).

    Single-value, 3-way counterpart to _day_type() (moved from api/main.py,
    issue #107) -- used by /stops/{id}/context, which needs the display
    label (공휴일 vs 주말 kept separate), unlike _day_type()'s 2-way
    평일/주말+공휴일 grouping used for the correction-factor tables.
    """
    if date in holiday_dates:
        return "공휴일"
    dow = pd.to_datetime(str(date), format="%Y%m%d").dayofweek
    return "주말" if dow >= 5 else "평일"


def precipitation_type_from_asos(precipitation_mm: float, snowfall_cm: float) -> str:
    """맑음/비/눈 근사 라벨(과거 관측 ASOS 데이터 기준). Moved from api/main.py (issue #107)."""
    if snowfall_cm > 0:
        return "눈"
    if precipitation_mm > 0:
        return "비"
    return "맑음"


class BoardingFactorUnavailable(Exception):
    """Raised when a correction-factor lookup has no row to compute from --
    an unlisted stop_id, or a 요일×날씨×기온 group weekday_weather_factor has
    no column for (issue #137). Callers should catch this rather than let
    the underlying .iloc[0]/KeyError surface as a 500."""


def boarding_factor_for_labels(
    weekday_weather_factor: pd.DataFrame,
    stop_id: int,
    weekday_group: str,
    weather_group: str,
    temp_group: str,
) -> float:
    """보정계수_승차 for one stop's (요일구분, 날씨구분, 기온구분) group. Moved from
    api/main.py (issue #107); takes the parquet DataFrame directly rather
    than api/data.py's CorridorData, so features/ doesn't depend on api/.
    """
    if (weekday_group, weather_group, temp_group) == _BASELINE_GROUP:
        return 1.0
    return _factor_for_labels(
        weekday_weather_factor, stop_id, "보정계수_승차", weekday_group, weather_group, temp_group
    )


def normalized_boarding_factor_for_labels(
    weekday_weather_factor: pd.DataFrame,
    stop_id: int,
    weekday_group: str,
    weather_group: str,
    temp_group: str,
) -> float:
    """보정계수_승차_정규화 for one stop's group -- the factor to multiply into W.

    Use this, not boarding_factor_for_labels(), whenever the factor scales an
    estimate rather than describing it in prose: these ratios average 1.0 over
    the stop's own history, so they don't double-count the weather already
    baked into B_r (see _add_normalized_boarding_factors). The baseline group
    has no 1.0 shortcut here -- it is rescaled like every other group.
    """
    return _factor_for_labels(
        weekday_weather_factor,
        stop_id,
        "보정계수_승차_정규화",
        weekday_group,
        weather_group,
        temp_group,
    )


def _factor_for_labels(
    weekday_weather_factor: pd.DataFrame,
    stop_id: int,
    value: str,
    weekday_group: str,
    weather_group: str,
    temp_group: str,
) -> float:
    factor_row = weekday_weather_factor[weekday_weather_factor["표준버스정류장ID"] == stop_id]
    if factor_row.empty:
        raise BoardingFactorUnavailable(f"no weekday_weather_factor row for stop {stop_id}")
    column = factor_column_name(value, weekday_group, weather_group, temp_group)
    if column not in factor_row.columns:
        raise BoardingFactorUnavailable(
            f"no {column!r} column in weekday_weather_factor for stop {stop_id}"
        )
    return float(factor_row[column].iloc[0])


def congestion_note(day_type: str, boarding_factor: float) -> str:
    """Human-readable explanation of the day-type correction factor. Moved
    from api/main.py (issue #107).

    boarding_factor is 보정계수_승차 (해당 요일×날씨×기온 그룹 평균승차 / 기준선
    평균승차) from weekday_weather_factor.parquet, via boarding_factor_for_labels().
    """
    if day_type == "평일":
        return "평일이라 평소와 비슷한 혼잡도가 예상됩니다."
    percent = round(abs(boarding_factor - 1.0) * 100)
    direction = "낮을" if boarding_factor < 1.0 else "높을"
    return f"{day_type}이라 평소보다 혼잡도가 약 {percent}% {direction} 것으로 예상됩니다."


def build_weekday_weather_factor(features_daily: pd.DataFrame) -> pd.DataFrame:
    """Per-stop 요일구분×날씨구분×기온구분(12그룹) average ratio for 승차/하차.

    Baseline is 평일·맑음·보통 (largest sample, and the natural "business
    as usual" reference point).

    12 groups over a 3-year corridor (issue: temperature added, 2023-07
    range extension) keeps every group's sample size >= ~30 days; the
    rarest combination (주말+공휴일 x 강수, 3 temp terciles) is ~34-46
    days/group. See 극단치주의 for any that still land outside the
    trusted ratio band.
    """
    group_cols = ["표준버스정류장ID", "정류장명", "요일구분", "날씨구분", "기온구분"]
    grouped = (
        features_daily.groupby(group_cols, observed=True)
        .agg(평균승차=("승차", "mean"), 평균하차=("하차", "mean"), 표본수=("사용일자", "count"))
        .reset_index()
    )
    pivot = grouped.pivot(
        index=["표준버스정류장ID", "정류장명"],
        columns=["요일구분", "날씨구분", "기온구분"],
        values=["평균승차", "평균하차", "표본수"],
    )
    pivot.columns = [
        factor_column_name(value, day, weather, temp) for value, day, weather, temp in pivot.columns
    ]
    pivot = pivot.reset_index()

    base_board = pivot[factor_column_name("평균승차", *_BASELINE_GROUP)]
    base_alight = pivot[factor_column_name("평균하차", *_BASELINE_GROUP)]
    all_groups = [
        (day, weather, temp)
        for day in ("평일", "주말+공휴일")
        for weather in ("맑음", "강수")
        for temp in _TEMP_LABELS
    ]
    non_baseline = [group for group in all_groups if group != _BASELINE_GROUP]
    for day, weather, temp in non_baseline:
        pivot[factor_column_name("보정계수_승차", day, weather, temp)] = (
            pivot[factor_column_name("평균승차", day, weather, temp)] / base_board
        )
        pivot[factor_column_name("보정계수_하차", day, weather, temp)] = (
            pivot[factor_column_name("평균하차", day, weather, temp)] / base_alight
        )

    ratio_cols = [c for c in pivot.columns if c.startswith("보정계수_")]
    in_range = pivot[ratio_cols].apply(lambda s: s.between(_OUTLIER_LOW, _OUTLIER_HIGH))
    pivot["극단치주의"] = ~in_range.all(axis=1)

    # 극단치주의는 위 원본 비율에 대한 판정이라 정규화 컬럼을 붙이기 전에 끝낸다.
    for value in ("승차", "하차"):
        _add_normalized_factors(pivot, all_groups, value)

    return pivot.sort_values("표준버스정류장ID").reset_index(drop=True)


def _add_normalized_factors(
    pivot: pd.DataFrame, all_groups: list[tuple[str, str, str]], value: str
) -> None:
    """Add 보정계수_<value>_정규화_* : the same ratios rescaled to average 1.0.

    보정계수_승차 is each group's mean boarding over the 평일·맑음·보통
    baseline's. Multiplying it straight into an estimate is only valid if the
    estimate is itself on that baseline -- but wait_population's B_r is a
    12-month daily average pooled over every weekday and weather condition
    (ingest/oa12913.py), so the baseline-relative ratio would shift every W by
    the gap between "baseline day" and "average day" on top of the weather
    effect it is supposed to carry.

    Dividing every group by the same per-stop constant fixes that while
    leaving the ratios *between* groups untouched: weight each group's ratio
    by 표본수 (how many days of history actually fell in it) and rescale so
    that weighted average is exactly 1. The correction then only redistributes
    W across conditions instead of moving its overall level.

    Baseline included -- it is 1.0 before rescaling, so it lands near but not
    exactly 1.0 after, and callers must look it up like any other group.
    """
    raw = {
        group: (
            pd.Series(1.0, index=pivot.index)
            if group == _BASELINE_GROUP
            else pivot[factor_column_name(f"보정계수_{value}", *group)]
        )
        for group in all_groups
    }
    ratios = pd.concat(raw.values(), axis=1, ignore_index=True)
    weights = pd.concat(
        [pivot[factor_column_name("표본수", *group)] for group in all_groups],
        axis=1,
        ignore_index=True,
    )
    # A group this stop has no history for contributes to neither side, so a
    # stop missing one still normalizes over the groups it does have.
    covered = weights.where(ratios.notna())
    normalizer = (covered * ratios).sum(axis=1) / covered.sum(axis=1)

    for group in all_groups:
        pivot[factor_column_name(f"보정계수_{value}_정규화", *group)] = raw[group] / normalizer


def run(processed_dir: Path) -> None:
    """Build corridor_features_daily.parquet and weekday_weather_factor.parquet."""
    corridor_daily = pd.read_parquet(processed_dir / "corridor_daily.parquet")
    weather_daily = pd.read_parquet(processed_dir / "weather_daily.parquet")
    holiday_daily = pd.read_parquet(processed_dir / "holiday_daily.parquet")

    features_daily = build_features_daily(corridor_daily, weather_daily, holiday_daily)
    weather_factor = build_weekday_weather_factor(features_daily)

    features_daily.to_parquet(processed_dir / "corridor_features_daily.parquet", index=False)
    weather_factor.to_parquet(processed_dir / "weekday_weather_factor.parquet", index=False)


if __name__ == "__main__":
    run(Path("data/processed"))
