"""Tests for the OA-12913 corridor builder."""

import pandas as pd

from stationcast.ingest.oa12913 import build_corridor_hourly, build_corridor_stops


def _boarding_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "표준버스정류장ID": [100000389, 100000389, 999999999],
            "역명": ["종로2가(00063)", "종로2가(00073)", "다른정류장(00001)"],
            "버스정류장ARS번호": ["01014", "01014", "09999"],
            "0시승차총승객수": [10, 5, 3],
            "0시하차총승객수": [1, 2, 4],
            "1시승차총승객수": [7, 3, 1],
            "1시하차총승객수": [0, 1, 2],
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


def test_build_corridor_hourly_sums_across_routes_and_strips_stop_ids() -> None:
    result = build_corridor_hourly(_boarding_df(), stop_ids=(100000389,))

    assert list(result["표준버스정류장ID"].unique()) == [100000389]
    assert set(result["정류장명"]) == {"종로2가"}
    assert len(result) == 2  # two hours

    hour0 = result[result["시간대"] == 0].iloc[0]
    assert hour0["승차"] == 15  # 10 + 5
    assert hour0["하차"] == 3  # 1 + 2

    hour1 = result[result["시간대"] == 1].iloc[0]
    assert hour1["승차"] == 10  # 7 + 3
    assert hour1["하차"] == 1  # 0 + 1


def test_build_corridor_stops_merges_name_ars_and_coordinates() -> None:
    result = build_corridor_stops(_boarding_df(), _coord_df(), stop_ids=(100000389,))

    assert len(result) == 1
    row = result.iloc[0]
    assert row["표준버스정류장ID"] == 100000389
    assert row["정류장명"] == "종로2가"
    assert row["ARS번호"] == "01014"
    assert row["X좌표"] == 126.986535
    assert row["정류소 타입"] == "중앙차로"
