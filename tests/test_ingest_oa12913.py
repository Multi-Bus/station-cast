"""Tests for the OA-12913 corridor builder."""

import pandas as pd

from stationcast.ingest.oa12913 import build_corridor_hourly, build_corridor_stops


def _boarding_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "표준버스정류장ID": [100000389, 100000389, 100000389, 999999999],
            "노선번호": ["150", "271", "N15", "150"],
            "역명": ["종로2가(00063)", "종로2가(00073)", "종로2가(00099)", "다른정류장(00001)"],
            "버스정류장ARS번호": ["01014", "01014", "01014", "09999"],
            "사용년월": [202606, 202606, 202606, 202606],  # June 2026 -> 30 days
            # values are x30 of the old fixture so that, after the
            # daily-average normalization, the expected sums are unchanged.
            # The N15 (night bus) row's large values would blow up the
            # expected totals below if it weren't excluded.
            "0시승차총승객수": [300, 150, 9000, 90],
            "0시하차총승객수": [30, 60, 9000, 120],
            "1시승차총승객수": [210, 90, 9000, 30],
            "1시하차총승객수": [0, 30, 9000, 60],
        }
    )


def _coord_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "정류소번호": [100000389],
            "X좌표": [126.986535],
            "Y좌표": [37.570238],
            "정류소 타입": ["중앙차로"],
        }
    )


def test_build_corridor_hourly_sums_across_routes_and_excludes_night_buses() -> None:
    result = build_corridor_hourly(_boarding_df(), stop_ids=(100000389,))

    assert list(result["표준버스정류장ID"].unique()) == [100000389]
    assert set(result["정류장명"]) == {"종로2가"}
    assert len(result) == 2  # two hours

    # N15's huge values (9000) must not appear in either hour's total --
    # if the night-bus filter breaks, these assertions catch it.
    hour0 = result[result["시간대"] == 0].iloc[0]
    assert hour0["승차"] == 15  # (300 + 150) / 30, N15 excluded
    assert hour0["하차"] == 3  # (30 + 60) / 30, N15 excluded

    hour1 = result[result["시간대"] == 1].iloc[0]
    assert hour1["승차"] == 10  # (210 + 90) / 30, N15 excluded
    assert hour1["하차"] == 1  # (0 + 30) / 30, N15 excluded


def test_build_corridor_hourly_normalizes_by_days_in_month() -> None:
    # 202602 = Feb 2026 (not a leap year -> 28 days). Values only divide
    # evenly by 28, not 30, to catch any code that hardcodes 30.
    df = pd.DataFrame(
        {
            "표준버스정류장ID": [100000389],
            "노선번호": ["150"],
            "역명": ["종로2가(00063)"],
            "버스정류장ARS번호": ["01014"],
            "사용년월": [202602],
            "0시승차총승객수": [280],
            "0시하차총승객수": [56],
        }
    )

    result = build_corridor_hourly(df, stop_ids=(100000389,))

    assert result.iloc[0]["승차"] == 10.0  # 280 / 28
    assert result.iloc[0]["하차"] == 2.0  # 56 / 28


def test_build_corridor_stops_merges_name_ars_and_coordinates() -> None:
    result = build_corridor_stops(_boarding_df(), _coord_df(), stop_ids=(100000389,))

    assert len(result) == 1
    row = result.iloc[0]
    assert row["표준버스정류장ID"] == 100000389
    assert row["정류장명"] == "종로2가"
    assert row["ARS번호"] == "01014"
    assert row["X좌표"] == 126.986535
    assert row["정류소 타입"] == "중앙차로"
