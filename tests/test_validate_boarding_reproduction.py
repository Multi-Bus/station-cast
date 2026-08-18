"""Tests for daily boarding reproduction MAPE + sensitivity (issue #16)."""

import pandas as pd
import pytest

from stationcast.validate.boarding_reproduction import (
    KNOWN_NIGHT_BUS_ONLY_DATES,
    build_boarding_reproduction_report,
    per_stop_mape,
    summarize_mape,
)

STOP = 100000389


def _corridor_daily() -> pd.DataFrame:
    # Stop A: three normal weekday-sunny-mild days (100, 120, 80) plus one
    # known-anomaly date with a near-zero count that would dominate MAPE.
    return pd.DataFrame(
        {
            "표준버스정류장ID": [STOP, STOP, STOP, STOP],
            "정류장명": ["종로2가", "종로2가", "종로2가", "종로2가"],
            "사용일자": [20250701, 20250702, 20250703, KNOWN_NIGHT_BUS_ONLY_DATES[0]],
            "승차": [100.0, 120.0, 80.0, 2.0],
            "하차": [50.0, 60.0, 40.0, 1.0],
        }
    )


def _features_daily() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "표준버스정류장ID": [STOP, STOP, STOP, STOP],
            "정류장명": ["종로2가", "종로2가", "종로2가", "종로2가"],
            "사용일자": [20250701, 20250702, 20250703, KNOWN_NIGHT_BUS_ONLY_DATES[0]],
            "승차": [100.0, 120.0, 80.0, 2.0],
            "요일구분": ["평일", "평일", "평일", "평일"],
            "날씨구분": ["맑음", "맑음", "맑음", "맑음"],
            "기온구분": ["보통", "보통", "보통", "보통"],
        }
    )


def _weekday_holiday_factor() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "표준버스정류장ID": [STOP],
            "정류장명": ["종로2가"],
            "평균승차_평일": [100.0],
            "평균승차_주말+공휴일": [60.0],
        }
    )


def _weekday_weather_factor() -> pd.DataFrame:
    row = {"표준버스정류장ID": STOP, "정류장명": "종로2가"}
    for day in ("평일", "주말+공휴일"):
        for weather in ("맑음", "강수"):
            for temp in ("저온", "보통", "고온"):
                row[f"평균승차_{day}_{weather}_{temp}"] = 100.0
    row["평균승차_평일_맑음_보통"] = 100.0  # matches the fixture's actual mean exactly
    return pd.DataFrame([row])


def test_build_report_joins_all_three_predictions() -> None:
    report = build_boarding_reproduction_report(
        _corridor_daily(), _features_daily(), _weekday_holiday_factor(), _weekday_weather_factor()
    )

    assert len(report) == 4
    row = report[report["사용일자"] == 20250701].iloc[0]
    assert row["실측_승차"] == pytest.approx(100.0)
    assert row["요일보정_예측승차"] == pytest.approx(100.0)
    assert row["요일날씨기온보정_예측승차"] == pytest.approx(100.0)


def test_summarize_mape_excludes_known_anomaly_by_default() -> None:
    report = build_boarding_reproduction_report(
        _corridor_daily(), _features_daily(), _weekday_holiday_factor(), _weekday_weather_factor()
    )

    # With the anomaly excluded, only the three normal days remain, and the
    # 요일+날씨+기온 prediction (100) exactly matches two of them (100, and
    # is off by 20 for the other two) -- nowhere near the anomaly's ~4,900%
    # single-day error.
    clean = summarize_mape(report, exclude_known_anomalies=True)
    assert clean["요일날씨기온보정_MAPE"] < 30.0

    raw = summarize_mape(report, exclude_known_anomalies=False)
    assert raw["요일날씨기온보정_MAPE"] > clean["요일날씨기온보정_MAPE"]


def test_per_stop_mape_excludes_known_anomaly_by_default() -> None:
    report = build_boarding_reproduction_report(
        _corridor_daily(), _features_daily(), _weekday_holiday_factor(), _weekday_weather_factor()
    )
    by_stop = per_stop_mape(report)

    assert len(by_stop) == 1
    assert by_stop.iloc[0]["표준버스정류장ID"] == STOP
    assert by_stop.iloc[0]["요일날씨기온보정_MAPE"] < 30.0
