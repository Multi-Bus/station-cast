"""Tests for the KMA ASOS daily weather collector."""

import pandas as pd

from stationcast.ingest.weather import build_weather_daily


def _raw_weather_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "지점": [108, 108],
            "지점명": ["서울", "서울"],
            "일시": ["2025-07-01", "2025-12-04"],
            "평균기온(°C)": [28.5, -1.2],
            "최고기온(°C)": [33.0, 2.0],
            "최저기온(°C)": [24.0, -5.0],
            "일강수량(mm)": [5.0, float("nan")],  # rained on day 1, dry on day 2
            "평균 상대습도(%)": [70.0, 55.0],
            "일 최심신적설(cm)": [float("nan"), 5.1],  # no snow day 1, snowed day 2
            "평균 풍속(m/s)": [2.1, 3.4],
            "최대 풍속(m/s)": [4.5, 7.2],
        }
    )


def test_build_weather_daily_renames_and_converts_date() -> None:
    result = build_weather_daily(_raw_weather_df())

    assert list(result["사용일자"]) == [20250701, 20251204]
    assert list(result.columns) == [
        "사용일자",
        "평균기온",
        "최고기온",
        "최저기온",
        "강수량",
        "습도",
        "신적설",
        "평균풍속",
        "최대풍속",
    ]


def test_build_weather_daily_fills_no_event_days_with_zero() -> None:
    result = build_weather_daily(_raw_weather_df())

    # day 1: rained, no snow -> 강수량 kept, 신적설 filled to 0
    day1 = result[result["사용일자"] == 20250701].iloc[0]
    assert day1["강수량"] == 5.0
    assert day1["신적설"] == 0.0

    # day 2: dry, snowed -> 강수량 filled to 0, 신적설 kept
    day2 = result[result["사용일자"] == 20251204].iloc[0]
    assert day2["강수량"] == 0.0
    assert day2["신적설"] == 5.1
