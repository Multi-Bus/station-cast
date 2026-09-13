"""Tests for the corridor route schedule builder."""

import pandas as pd

from stationcast.ingest.route_schedule import build_corridor_route_schedule


def _boarding_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "표준버스정류장ID": [100000389, 100000389, 100000389, 999999999],
            "역명": [
                "종로2가(00063)",
                "종로2가(00090)",
                "종로2가(00099)",
                "다른정류장(00001)",
            ],
            # "새벽A160" is a dawn route (different from 심야 night buses)
            # with no published schedule; "N15" is a night bus, flagged via
            # is_night_bus rather than excluded.
            "노선번호": ["150", "새벽A160", "N15", "999"],
        }
    )


def _route_schedule() -> pd.DataFrame:
    # "150" is jointly operated by two companies (공동배차): duplicated
    # across day types with identical values, same shape as the real
    # source file. "새벽A160" has a published 배차간격 of 0 (no schedule
    # registered yet).
    route_150 = {"유형": "간선", "배차간격": 8, "인가대수": 20, "최소배차": 6, "최대배차": 10}
    route_dawn = {"유형": "지선", "배차간격": 0, "인가대수": 3, "최소배차": 0, "최대배차": 0}

    rows = []
    for day_type in ("평일", "토요일", "공휴일"):
        rows.append({"노선번호": "150", "요일유형": day_type, **route_150})
        rows.append({"노선번호": "150", "요일유형": day_type, **route_150})
        rows.append({"노선번호": "새벽A160", "요일유형": day_type, **route_dawn})
    return pd.DataFrame(rows)


def test_build_corridor_route_schedule_dedupes_joint_operation_routes() -> None:
    result = build_corridor_route_schedule(_boarding_df(), _route_schedule(), stop_ids=(100000389,))

    # "150", "새벽A160", "N15" x 3 day types = 9 rows; the doubled "150"
    # rows (공동배차 두 회사) must collapse to one row per day type, not two.
    assert len(result) == 9
    assert set(result["노선번호"]) == {"150", "새벽A160", "N15"}
    assert set(result["정류장명"]) == {"종로2가"}

    weekday_150 = result[(result["노선번호"] == "150") & (result["요일유형"] == "평일")]
    assert len(weekday_150) == 1
    assert weekday_150.iloc[0]["배차간격"] == 8
    assert bool(weekday_150.iloc[0]["배차정보없음"]) is False
    assert bool(weekday_150.iloc[0]["is_night_bus"]) is False


def test_build_corridor_route_schedule_flags_zero_headway_as_missing() -> None:
    result = build_corridor_route_schedule(_boarding_df(), _route_schedule(), stop_ids=(100000389,))

    dawn_route = result[result["노선번호"] == "새벽A160"]
    assert len(dawn_route) == 3  # one per day type
    assert dawn_route["배차정보없음"].all()
    assert not dawn_route["is_night_bus"].any()


def test_build_corridor_route_schedule_flags_night_bus_with_missing_headway() -> None:
    result = build_corridor_route_schedule(_boarding_df(), _route_schedule(), stop_ids=(100000389,))

    night_bus = result[result["노선번호"] == "N15"]
    assert len(night_bus) == 3  # one per day type
    assert night_bus["is_night_bus"].all()
    assert night_bus["배차정보없음"].all()  # fixture has no schedule row for N15
