"""Tests for the OA-12912 daily corridor builder."""

import pandas as pd

from stationcast.ingest.oa12912 import build_corridor_daily


def _daily_df(usage_date: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "사용일자": [usage_date, usage_date, usage_date, usage_date],
            "노선번호": ["150", "201", "N15", "999"],
            "표준버스정류장ID": [100000389, 100000389, 100000389, 999999999],
            "역명": [
                "종로2가(00063)",
                "종로2가(00090)",
                "종로2가(00099)",
                "다른정류장(00001)",
            ],
            # N15's large values would blow up the expected totals below
            # if the night-bus filter didn't exclude it.
            "승차총승객수": [100, 50, 9000, 30],
            "하차총승객수": [80, 40, 9000, 20],
        }
    )


def test_build_corridor_daily_sums_across_routes_and_excludes_night_buses() -> None:
    combined = pd.concat([_daily_df(20260601), _daily_df(20260701)], ignore_index=True)

    result = build_corridor_daily(combined, stop_ids=(100000389,))

    assert list(result["표준버스정류장ID"].unique()) == [100000389]
    assert set(result["정류장명"]) == {"종로2가"}
    assert len(result) == 2  # one row per (stop, date)

    june_row = result[result["사용일자"] == 20260601].iloc[0]
    assert june_row["승차"] == 150  # 100 + 50, N15 excluded
    assert june_row["하차"] == 120  # 80 + 40, N15 excluded

    july_row = result[result["사용일자"] == 20260701].iloc[0]
    assert july_row["승차"] == 150
    assert july_row["하차"] == 120


def test_build_corridor_daily_keeps_one_series_when_stop_name_changes() -> None:
    old_name_day = pd.DataFrame(
        {
            "사용일자": [20250701],
            "노선번호": ["150"],
            "표준버스정류장ID": [101000042],
            "역명": ["해운센터.롯데영플라자(00001)"],
            "승차총승객수": [100],
            "하차총승객수": [80],
        }
    )
    new_name_day = pd.DataFrame(
        {
            "사용일자": [20260601],
            "노선번호": ["150"],
            "표준버스정류장ID": [101000042],
            "역명": ["소공동.롯데영플라자(00001)"],
            "승차총승객수": [200],
            "하차총승객수": [150],
        }
    )
    combined = pd.concat([old_name_day, new_name_day], ignore_index=True)

    result = build_corridor_daily(combined, stop_ids=(101000042,))

    assert len(result) == 2  # two dates, one stop
    # the rename must not fragment the stop's identity: every row carries
    # a single representative (most recent) name
    assert set(result["정류장명"]) == {"소공동.롯데영플라자"}
