"""Weekday/holiday and weather calendar features (issue #10).

Joins corridor_daily.parquet (per-stop daily boarding/alighting, from
ingest/oa12912.py) with weather_daily.parquet and holiday_daily.parquet
on 사용일자, labels each date 평일 or 주말+공휴일 (weekends are computed
directly from the date; holidays come from holiday_daily.parquet), and
derives a per-stop correction factor between the two groups.
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


def build_features_daily(
    corridor_daily: pd.DataFrame,
    weather_daily: pd.DataFrame,
    holiday_daily: pd.DataFrame,
) -> pd.DataFrame:
    """Join corridor/weather/holiday data and attach a 요일구분 label."""
    holiday_dates = set(holiday_daily["사용일자"])
    merged = corridor_daily.merge(weather_daily, on="사용일자", how="left")
    merged["요일구분"] = _day_type(merged["사용일자"], holiday_dates)
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


def run(processed_dir: Path) -> None:
    """Build corridor_features_daily.parquet and weekday_holiday_factor.parquet."""
    corridor_daily = pd.read_parquet(processed_dir / "corridor_daily.parquet")
    weather_daily = pd.read_parquet(processed_dir / "weather_daily.parquet")
    holiday_daily = pd.read_parquet(processed_dir / "holiday_daily.parquet")

    features_daily = build_features_daily(corridor_daily, weather_daily, holiday_daily)
    factor = build_weekday_holiday_factor(features_daily)

    features_daily.to_parquet(processed_dir / "corridor_features_daily.parquet", index=False)
    factor.to_parquet(processed_dir / "weekday_holiday_factor.parquet", index=False)


if __name__ == "__main__":
    run(Path("data/processed"))
