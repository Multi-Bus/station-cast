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
            # "새벽A160" is a dawn route (different from 심야 night buses,
            # not excluded here) with no published schedule; "N15" is a
            # night bus and must be excluded entirely.
            "노선번호": ["150", "새벽A160", "N15", "999"],
        }
    )


def _route_schedule() -> pd.DataFrame:
    # "150" is jointly operated by two companies (공동배차): duplicated
    # across day types with identical values, same shape as the real
    # source file. "새벽A160" has a published 배차간격 of 0 (no schedule
    # registered yet).
    route_150 = {"배차간격": 8, "인가대수": 20, "최소배차": 6, "최대배차": 10}
    route_dawn = {"배차간격": 0, "인가대수": 3, "최소배차": 0, "최대배차": 0}

    rows = []
    for day_type in ("평일", "토요일", "공휴일"):
        rows.append({"노선번호": "150", "요일유형": day_type, **route_150})
        rows.append({"노선번호": "150", "요일유형": day_type, **route_150})
        rows.append({"노선번호": "새벽A160", "요일유형": day_type, **route_dawn})
    return pd.DataFrame(rows)


def test_build_corridor_route_schedule_dedupes_joint_operation_routes() -> None:
    result = build_corridor_route_schedule(_boarding_df(), _route_schedule(), stop_ids=(100000389,))

    # "150" and "새벽A160" x 3 day types = 6 rows; "N15" (night bus) must
    # be excluded entirely, and the doubled "150" rows (공동배차 두 회사)
    # must collapse to one row per day type, not two.
    assert len(result) == 6
    assert "N15" not in set(result["노선번호"])
    assert set(result["정류장명"]) == {"종로2가"}

    weekday_150 = result[(result["노선번호"] == "150") & (result["요일유형"] == "평일")]
    assert len(weekday_150) == 1
    assert weekday_150.iloc[0]["배차간격"] == 8
    assert bool(weekday_150.iloc[0]["배차정보없음"]) is False


def test_build_corridor_route_schedule_flags_zero_headway_as_missing() -> None:
    result = build_corridor_route_schedule(_boarding_df(), _route_schedule(), stop_ids=(100000389,))

    dawn_route = result[result["노선번호"] == "새벽A160"]
    assert len(dawn_route) == 3  # one per day type
    assert dawn_route["배차정보없음"].all()
