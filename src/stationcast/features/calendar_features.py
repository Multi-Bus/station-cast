"""Weekday/holiday and weather calendar features (issue #10).

Joins corridor_daily.parquet (per-stop daily boarding/alighting, from
ingest/oa12912.py) with weather_daily.parquet and holiday_daily.parquet
on 사용일자, labels each date 평일 or 주말+공휴일 (weekends are computed
directly from the date; holidays come from holiday_daily.parquet) and
강수 or 맑음, and derives per-stop correction factors from those labels.
"""

from pathlib import Path

import pandas as pd

_WEEKEND_DAYOFWEEK = {5, 6}  # Saturday, Sunday (pandas dayofweek: Monday=0)

# Correction factors outside this range are flagged for manual review
# rather than silently trusted (agreed post-hoc outlier check).
_OUTLIER_LOW = 0.5
_OUTLIER_HIGH = 2.0


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


def build_features_daily(
    corridor_daily: pd.DataFrame,
    weather_daily: pd.DataFrame,
    holiday_daily: pd.DataFrame,
) -> pd.DataFrame:
    """Join corridor/weather/holiday data and attach 요일구분/날씨구분 labels."""
    holiday_dates = set(holiday_daily["사용일자"])
    merged = corridor_daily.merge(weather_daily, on="사용일자", how="left")
    merged["요일구분"] = _day_type(merged["사용일자"], holiday_dates)
    merged["날씨구분"] = _weather_type(merged["강수량"], merged["신적설"])
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


def build_weekday_weather_factor(features_daily: pd.DataFrame) -> pd.DataFrame:
    """Per-stop 요일구분×날씨구분(4그룹) average ratio for 승차/하차.

    Baseline is 평일·맑음 (largest sample, and the natural "business as
    usual" reference point). Separate from build_weekday_holiday_factor's
    2-group (요일구분 only) output -- this is a distinct file so the
    existing weekday_holiday_factor.parquet consumers (e.g. the
    /stops/{id}/context API) are unaffected.
    """
    grouped = (
        features_daily.groupby(["표준버스정류장ID", "정류장명", "요일구분", "날씨구분"])
        .agg(평균승차=("승차", "mean"), 평균하차=("하차", "mean"), 표본수=("사용일자", "count"))
        .reset_index()
    )
    pivot = grouped.pivot(
        index=["표준버스정류장ID", "정류장명"],
        columns=["요일구분", "날씨구분"],
        values=["평균승차", "평균하차", "표본수"],
    )
    pivot.columns = [f"{value}_{day}_{weather}" for value, day, weather in pivot.columns]
    pivot = pivot.reset_index()

    base_board = pivot["평균승차_평일_맑음"]
    base_alight = pivot["평균하차_평일_맑음"]
    for day, weather in [("평일", "강수"), ("주말+공휴일", "맑음"), ("주말+공휴일", "강수")]:
        pivot[f"보정계수_승차_{day}_{weather}"] = pivot[f"평균승차_{day}_{weather}"] / base_board
        pivot[f"보정계수_하차_{day}_{weather}"] = pivot[f"평균하차_{day}_{weather}"] / base_alight

    ratio_cols = [c for c in pivot.columns if c.startswith("보정계수_")]
    in_range = pivot[ratio_cols].apply(lambda s: s.between(_OUTLIER_LOW, _OUTLIER_HIGH))
    pivot["극단치주의"] = ~in_range.all(axis=1)

    return pivot.sort_values("표준버스정류장ID").reset_index(drop=True)


def run(processed_dir: Path) -> None:
    """Build corridor_features_daily.parquet, weekday_holiday_factor.parquet, and
    weekday_weather_factor.parquet."""
    corridor_daily = pd.read_parquet(processed_dir / "corridor_daily.parquet")
    weather_daily = pd.read_parquet(processed_dir / "weather_daily.parquet")
    holiday_daily = pd.read_parquet(processed_dir / "holiday_daily.parquet")

    features_daily = build_features_daily(corridor_daily, weather_daily, holiday_daily)
    factor = build_weekday_holiday_factor(features_daily)
    weather_factor = build_weekday_weather_factor(features_daily)

    features_daily.to_parquet(processed_dir / "corridor_features_daily.parquet", index=False)
    factor.to_parquet(processed_dir / "weekday_holiday_factor.parquet", index=False)
    weather_factor.to_parquet(processed_dir / "weekday_weather_factor.parquet", index=False)


if __name__ == "__main__":
    run(Path("data/processed"))
