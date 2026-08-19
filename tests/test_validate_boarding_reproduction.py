"""Tests for daily boarding reproduction MAPE + sensitivity (issue #16)."""

import pandas as pd
import pytest

from stationcast.validate.boarding_reproduction import (
    KNOWN_NIGHT_BUS_ONLY_DATES,
    TRAIN_TEST_CUTOFF,
    build_boarding_reproduction_report,
    per_stop_mape,
    summarize_mape,
)

STOP = 100000389
NAME = "종로2가"


def _train_rows() -> list[dict]:
    # One row per (요일구분, 날씨구분, 기온구분) combo so demand_factors' group
    # means are defined for all 12 groups, like the real 3-year corridor data
    # -- except 평일/맑음/보통, which gets three rows (100, 120, 80) so the
    # baseline mean (100) differs visibly from a single-row group.
    rows = []
    date = 20250601
    for day in ("평일", "주말+공휴일"):
        for weather in ("맑음", "강수"):
            for temp in ("저온", "보통", "고온"):
                is_baseline_group = (day, weather, temp) == ("평일", "맑음", "보통")
                values = [100.0, 120.0, 80.0] if is_baseline_group else [100.0]
                for value in values:
                    rows.append(
                        {
                            "표준버스정류장ID": STOP,
                            "정류장명": NAME,
                            "사용일자": date,
                            "승차": value,
                            "하차": value / 2,
                            "요일구분": day,
                            "날씨구분": weather,
                            "기온구분": temp,
                        }
                    )
                    date += 1
    assert date - 1 < TRAIN_TEST_CUTOFF
    return rows


def _test_rows() -> list[dict]:
    # All 평일/맑음/보통, matching the train group whose mean is exactly 100.
    return [
        {
            "표준버스정류장ID": STOP,
            "정류장명": NAME,
            "사용일자": 20250701,
            "승차": 100.0,
            "하차": 50.0,
            "요일구분": "평일",
            "날씨구분": "맑음",
            "기온구분": "보통",
        },
        {
            "표준버스정류장ID": STOP,
            "정류장명": NAME,
            "사용일자": 20250702,
            "승차": 90.0,
            "하차": 45.0,
            "요일구분": "평일",
            "날씨구분": "맑음",
            "기온구분": "보통",
        },
        {
            "표준버스정류장ID": STOP,
            "정류장명": NAME,
            "사용일자": KNOWN_NIGHT_BUS_ONLY_DATES[0],
            "승차": 2.0,
            "하차": 1.0,
            "요일구분": "평일",
            "날씨구분": "맑음",
            "기온구분": "보통",
        },
    ]


def _features_daily() -> pd.DataFrame:
    return pd.DataFrame(_train_rows() + _test_rows())


def _corridor_daily() -> pd.DataFrame:
    cols = ["표준버스정류장ID", "정류장명", "사용일자", "승차", "하차"]
    return _features_daily()[cols]


def test_report_only_covers_test_split() -> None:
    report = build_boarding_reproduction_report(_corridor_daily(), _features_daily())

    assert len(report) == 3
    assert (report["사용일자"] >= TRAIN_TEST_CUTOFF).all()


def test_predictions_are_fit_on_train_split_only() -> None:
    report = build_boarding_reproduction_report(_corridor_daily(), _features_daily())

    row = report[report["사용일자"] == 20250701].iloc[0]
    assert row["실측_승차"] == pytest.approx(100.0)
    assert row["무보정_예측승차"] == pytest.approx(100.0)
    assert row["요일날씨기온보정_예측승차"] == pytest.approx(100.0)


def test_summarize_mape_excludes_known_anomaly_by_default() -> None:
    report = build_boarding_reproduction_report(_corridor_daily(), _features_daily())

    clean = summarize_mape(report, exclude_known_anomalies=True)
    assert clean["요일날씨기온보정_MAPE"] < 30.0

    raw = summarize_mape(report, exclude_known_anomalies=False)
    assert raw["요일날씨기온보정_MAPE"] > clean["요일날씨기온보정_MAPE"]


def test_per_stop_mape_excludes_known_anomaly_by_default() -> None:
    report = build_boarding_reproduction_report(_corridor_daily(), _features_daily())
    by_stop = per_stop_mape(report)

    assert len(by_stop) == 1
    assert by_stop.iloc[0]["표준버스정류장ID"] == STOP
    assert by_stop.iloc[0]["요일날씨기온보정_MAPE"] < 30.0
