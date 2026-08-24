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


def build_weekday_holiday_factor(features_daily: pd.DataFrame) -> pd.DataFrame:
    """Per-stop 평일 vs 주말+공휴일 average ratio for 승차/하차.

    Flags stops whose ratio falls outside [0.5, 2.0] via 극단치주의 for
    manual review (e.g., an unusually small or large swing).
    """
    grouped = (
        features_daily.groupby(["표준버스정류장ID", "정류장명", "요일구분"])
        .agg(평균승차=("승차", "mean"), 평균하차=("하차", "mean"), 표본수=("사용일자", "count"))
        .reset_index()
    )
    pivot = grouped.pivot(
        index=["표준버스정류장ID", "정류장명"],
        columns="요일구분",
        values=["평균승차", "평균하차", "표본수"],
    )
    pivot.columns = [f"{value}_{day_type}" for value, day_type in pivot.columns]
    pivot = pivot.reset_index()

    pivot["보정계수_승차"] = pivot["평균승차_주말+공휴일"] / pivot["평균승차_평일"]
    pivot["보정계수_하차"] = pivot["평균하차_주말+공휴일"] / pivot["평균하차_평일"]
    pivot["극단치주의"] = ~pivot["보정계수_승차"].between(_OUTLIER_LOW, _OUTLIER_HIGH)

    return pivot.sort_values("표준버스정류장ID").reset_index(drop=True)


def factor_column_name(value: str, day_type: str, weather_type: str, temp_type: str) -> str:
    """Build a 요일구분×날씨구분×기온구분 wide-format column name (issue #105).

    e.g. factor_column_name("보정계수_승차", "평일", "맑음", "보통")
    -> "보정계수_승차_평일_맑음_보통". Single source for this naming convention:
    api/main.py's lookup and validate/boarding_reproduction.py's parser both
    need to agree with whatever this module generates.
    """
    return f"{value}_{day_type}_{weather_type}_{temp_type}"


def build_weekday_weather_factor(features_daily: pd.DataFrame) -> pd.DataFrame:
    """Per-stop 요일구분×날씨구분×기온구분(12그룹) average ratio for 승차/하차.

    Baseline is 평일·맑음·보통 (largest sample, and the natural "business
    as usual" reference point). Separate from build_weekday_holiday_factor's
    2-group (요일구분 only) output -- this is a distinct file (the
    /stops/{id}/context API now reads this one instead, see issue #78).

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

    base_board = pivot[factor_column_name("평균승차", "평일", "맑음", "보통")]
    base_alight = pivot[factor_column_name("평균하차", "평일", "맑음", "보통")]
    non_baseline = [
        (day, weather, temp)
        for day in ("평일", "주말+공휴일")
        for weather in ("맑음", "강수")
        for temp in _TEMP_LABELS
        if not (day == "평일" and weather == "맑음" and temp == "보통")
    ]
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

    return pivot.sort_values("표준버스정류장ID").reset_index(drop=True)


def run(processed_dir: Path) -> None:
    """Build corridor_features_daily.parquet and weekday_weather_factor.parquet.

    build_weekday_holiday_factor()'s 2-group table is no longer written to
    disk: weekday_weather_factor already has 요일구분 as one of its three
    axes, and nothing has read the 2-group file since /stops/{id}/context
    switched over (issue #78). The function stays for ad-hoc weekday-only
    comparisons -- it just isn't part of the pipeline's output any more.
    """
    corridor_daily = pd.read_parquet(processed_dir / "corridor_daily.parquet")
    weather_daily = pd.read_parquet(processed_dir / "weather_daily.parquet")
    holiday_daily = pd.read_parquet(processed_dir / "holiday_daily.parquet")

    features_daily = build_features_daily(corridor_daily, weather_daily, holiday_daily)
    weather_factor = build_weekday_weather_factor(features_daily)

    features_daily.to_parquet(processed_dir / "corridor_features_daily.parquet", index=False)
    weather_factor.to_parquet(processed_dir / "weekday_weather_factor.parquet", index=False)


if __name__ == "__main__":
    run(Path("data/processed"))
