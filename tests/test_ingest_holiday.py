"""Tests for the 특일정보 holiday collector."""

import pandas as pd

from stationcast.ingest.holiday import build_holiday_daily


def _raw_holiday_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "dateKind": ["01", "01", "01", "01"],
            "dateName": ["어린이날", "부처님오신날", "광복절", "1월1일"],
            "isHoliday": ["Y", "Y", "Y", "Y"],
            "locdate": [20260505, 20260505, 20250815, 20250101],  # last row out of range
            "seq": [1, 2, 1, 1],
        }
    )


def test_build_holiday_daily_filters_to_corridor_range() -> None:
    result = build_holiday_daily(
        _raw_holiday_df(), start=20250701, end=20260630
    )

    # 20250101 is before the corridor start and must be dropped
    assert 20250101 not in set(result["사용일자"])
    assert set(result["사용일자"]) == {20260505, 20250815}


def test_build_holiday_daily_collapses_same_day_holidays() -> None:
    result = build_holiday_daily(
        _raw_holiday_df(), start=20250701, end=20260630
    )

    row = result[result["사용일자"] == 20260505].iloc[0]
    assert row["공휴일명"] == "어린이날·부처님오신날"
    assert len(result[result["사용일자"] == 20260505]) == 1  # one row, not two
