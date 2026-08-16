"""Tests for the weekday/holiday/weather calendar feature builder."""

import pandas as pd

from stationcast.features.calendar_features import (
    build_features_daily,
    build_weekday_holiday_factor,
    build_weekday_weather_factor,
)


def _corridor_daily() -> pd.DataFrame:
    # 20260601 = Monday (평일), 20260606 = Saturday (주말),
    # 20260101 = Thursday but a holiday (1월1일) -> 주말+공휴일
    return pd.DataFrame(
        {
            "표준버스정류장ID": [100000389, 100000389, 100000389],
            "정류장명": ["종로2가", "종로2가", "종로2가"],
            "사용일자": [20260601, 20260606, 20260101],
            "승차": [1000, 400, 300],
            "하차": [800, 350, 250],
        }
    )


def _weather_daily() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "사용일자": [20260601, 20260606, 20260101],
            "평균기온": [20.0, 22.0, -2.0],
            "강수량": [0.0, 5.0, 0.0],
            "신적설": [0.0, 0.0, 0.0],
        }
    )


def _holiday_daily() -> pd.DataFrame:
    return pd.DataFrame({"사용일자": [20260101], "공휴일명": ["1월1일"]})


def test_build_features_daily_labels_weekday_weekend_and_holiday() -> None:
    result = build_features_daily(_corridor_daily(), _weather_daily(), _holiday_daily())

    labels = dict(zip(result["사용일자"], result["요일구분"], strict=True))
    assert labels[20260601] == "평일"  # Monday, not a holiday
    assert labels[20260606] == "주말+공휴일"  # Saturday
    assert labels[20260101] == "주말+공휴일"  # Thursday, but a holiday

    assert "평균기온" in result.columns
    assert "강수량" in result.columns


def test_build_weekday_holiday_factor_computes_ratio_and_flags_outliers() -> None:
    features = build_features_daily(_corridor_daily(), _weather_daily(), _holiday_daily())
    factor = build_weekday_holiday_factor(features)

    row = factor[factor["표준버스정류장ID"] == 100000389].iloc[0]
    assert row["평균승차_평일"] == 1000
    assert row["평균승차_주말+공휴일"] == 350  # (400 + 300) / 2
    assert row["보정계수_승차"] == 0.35
    assert bool(row["극단치주의"]) is True  # 0.35 is below the 0.5 threshold


def _corridor_daily_weather_mix() -> pd.DataFrame:
    # 20260601 Mon 평일+맑음, 20260602 Tue 평일+강수,
    # 20260606 Sat 주말+맑음, 20260607 Sun 주말+강수 -- one day per group.
    return pd.DataFrame(
        {
            "표준버스정류장ID": [100000389] * 4,
            "정류장명": ["종로2가"] * 4,
            "사용일자": [20260601, 20260602, 20260606, 20260607],
            "승차": [1000, 600, 400, 200],
            "하차": [800, 500, 350, 150],
        }
    )


def _weather_daily_weather_mix() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "사용일자": [20260601, 20260602, 20260606, 20260607],
            "평균기온": [20.0, 18.0, 22.0, 19.0],
            "강수량": [0.0, 5.0, 0.0, 10.0],
            "신적설": [0.0, 0.0, 0.0, 0.0],
        }
    )


def test_build_weekday_weather_factor_computes_four_group_ratios() -> None:
    features = build_features_daily(
        _corridor_daily_weather_mix(), _weather_daily_weather_mix(), _holiday_daily()
    )
    factor = build_weekday_weather_factor(features)

    row = factor[factor["표준버스정류장ID"] == 100000389].iloc[0]
    assert row["평균승차_평일_맑음"] == 1000  # baseline
    assert row["평균승차_평일_강수"] == 600
    assert row["평균승차_주말+공휴일_맑음"] == 400
    assert row["평균승차_주말+공휴일_강수"] == 200

    assert row["보정계수_승차_평일_강수"] == 0.6
    assert row["보정계수_승차_주말+공휴일_맑음"] == 0.4
    assert row["보정계수_승차_주말+공휴일_강수"] == 0.2

    # 0.4 and 0.2 both fall below the 0.5 outlier threshold
    assert bool(row["극단치주의"]) is True
