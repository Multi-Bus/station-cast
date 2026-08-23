"""Tests for the weekday/holiday/weather calendar feature builder."""

import pandas as pd

from stationcast.features.demand_factors import (
    _temp_type,
    build_features_daily,
    build_weekday_holiday_factor,
    build_weekday_weather_factor,
    classify_temperature,
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
            "최고기온": [24.0, 26.0, 2.0],
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


def test_temp_type_uses_fixed_boundaries() -> None:
    temps = pd.Series([-8.2, 13.9, 14.0, 25.9, 26.0, 38.0])
    labels = _temp_type(temps)

    assert list(labels) == ["저온", "저온", "보통", "보통", "고온", "고온"]


def test_classify_temperature_matches_temp_type_at_the_same_boundaries() -> None:
    assert classify_temperature(13.9) == "저온"
    assert classify_temperature(14.0) == "보통"
    assert classify_temperature(25.9) == "보통"
    assert classify_temperature(26.0) == "고온"


def _corridor_daily_weather_temp_mix() -> pd.DataFrame:
    # One day per (요일구분 x 날씨구분 x 기온구분) combination -- 12 rows.
    # 평일 dates are weekdays; 주말+공휴일 dates are Sat/Sun. No holiday
    # dates are used so 요일구분 comes purely from day-of-week.
    return pd.DataFrame(
        {
            "표준버스정류장ID": [100000389] * 12,
            "정류장명": ["종로2가"] * 12,
            "사용일자": [
                20260601,  # 평일 맑음 저온 (Mon)
                20260602,  # 평일 강수 저온 (Tue)
                20260606,  # 주말+공휴일 맑음 저온 (Sat)
                20260607,  # 주말+공휴일 강수 저온 (Sun)
                20260603,  # 평일 맑음 보통 (Wed) -- baseline
                20260604,  # 평일 강수 보통 (Thu)
                20260613,  # 주말+공휴일 맑음 보통 (Sat)
                20260614,  # 주말+공휴일 강수 보통 (Sun)
                20260605,  # 평일 맑음 고온 (Fri)
                20260608,  # 평일 강수 고온 (Mon)
                20260620,  # 주말+공휴일 맑음 고온 (Sat)
                20260621,  # 주말+공휴일 강수 고온 (Sun)
            ],
            "승차": [900, 850, 400, 150, 1000, 950, 420, 180, 1100, 1050, 450, 200],
            "하차": [700, 650, 300, 100, 800, 750, 320, 140, 900, 850, 350, 160],
        }
    )


def _weather_daily_weather_temp_mix() -> pd.DataFrame:
    dates = [
        20260601,
        20260602,
        20260606,
        20260607,
        20260603,
        20260604,
        20260613,
        20260614,
        20260605,
        20260608,
        20260620,
        20260621,
    ]
    # 최고기온, straddling the fixed 13.9/25.9 boundaries for each intended group.
    temps = [5.0, 6.0, 7.0, 8.0, 18.0, 17.0, 19.0, 20.0, 30.0, 29.0, 31.0, 32.0]
    precip = [0.0, 5.0, 0.0, 10.0, 0.0, 3.0, 0.0, 6.0, 0.0, 2.0, 0.0, 4.0]
    return pd.DataFrame(
        {
            "사용일자": dates,
            "평균기온": temps,
            "최고기온": temps,
            "강수량": precip,
            "신적설": [0.0] * 12,
        }
    )


def test_build_weekday_weather_factor_computes_twelve_group_ratios() -> None:
    features = build_features_daily(
        _corridor_daily_weather_temp_mix(), _weather_daily_weather_temp_mix(), _holiday_daily()
    )
    factor = build_weekday_weather_factor(features)

    row = factor[factor["표준버스정류장ID"] == 100000389].iloc[0]
    assert row["평균승차_평일_맑음_보통"] == 1000  # baseline
    assert row["평균승차_주말+공휴일_강수_저온"] == 150
    assert row["평균승차_평일_강수_고온"] == 1050

    assert row["보정계수_승차_주말+공휴일_강수_저온"] == 0.15
    assert row["보정계수_승차_평일_강수_고온"] == 1.05

    # 0.15 falls well below the 0.5 outlier threshold
    assert bool(row["극단치주의"]) is True
