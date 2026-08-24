"""Tests for physical constraint checks — non-negativity and capacity (issue #5)."""

import pandas as pd
import pytest

from stationcast.validate.physical_constraints import (
    build_validation_report,
    capacity_violation_rate,
    capacity_violation_report,
    non_negativity_report,
    non_negativity_violation_rate,
)

STOP = 100000389


def _wait_df() -> pd.DataFrame:
    # Stop 1, hours 0,1,2: W = -5, 3, 0   -> 1/3 violations
    # Stop 2, hours 0,1,2: W = -2, -1, -4 -> 3/3 violations
    return pd.DataFrame(
        {
            "표준버스정류장ID": [1, 1, 1, 2, 2, 2],
            "정류장명": ["A", "A", "A", "B", "B", "B"],
            "시간대": [0, 1, 2, 0, 1, 2],
            "W": [-5.0, 3.0, 0.0, -2.0, -1.0, -4.0],
        }
    )


def _route_hourly() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "표준버스정류장ID": [STOP, STOP],
            "정류장명": ["종로2가", "종로2가"],
            "노선번호": ["150", "402"],
            "시간대": [18, 18],
            "승차": [30.0, 20.0],
        }
    )


def _route_schedule() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "표준버스정류장ID": [STOP, STOP],
            "노선번호": ["150", "402"],
            "요일유형": ["평일", "평일"],
            "배차간격": [6.0, 10.0],
            "배차정보없음": [False, False],
        }
    )


def test_non_negativity_violation_rate_across_whole_corridor() -> None:
    assert non_negativity_violation_rate(_wait_df()) == pytest.approx(4 / 6)


def test_non_negativity_violation_rate_rejects_empty() -> None:
    empty = pd.DataFrame(columns=["표준버스정류장ID", "정류장명", "시간대", "W"])
    with pytest.raises(ValueError, match="empty"):
        non_negativity_violation_rate(empty)


def test_non_negativity_report_per_stop() -> None:
    report = non_negativity_report(_wait_df())

    stop1 = report[report["표준버스정류장ID"] == 1].iloc[0]
    assert stop1["총_시간대수"] == 3
    assert stop1["위반_횟수"] == 1
    assert stop1["위반율"] == pytest.approx(1 / 3)

    stop2 = report[report["표준버스정류장ID"] == 2].iloc[0]
    assert stop2["총_시간대수"] == 3
    assert stop2["위반_횟수"] == 3
    assert stop2["위반율"] == pytest.approx(1.0)


def test_capacity_violation_report_no_violation_when_under_capacity() -> None:
    # route 150: 수송능력 = (60/6)*46 = 460, 승차 30 -- nowhere near capacity.
    report = capacity_violation_report(_route_hourly(), _route_schedule(), bus_capacity=46.0)

    assert (~report["위반"]).all()
    assert (report["이월"] == 0.0).all()

    route_150 = report[report["노선번호"] == "150"].iloc[0]
    assert route_150["수송능력"] == pytest.approx(460.0)


def test_capacity_violation_report_flags_boarding_over_capacity() -> None:
    # Force a tiny capacity so boarding clearly exceeds it: headway 6min,
    # bus_capacity 2 -> 수송능력 = (60/6)*2 = 20 < 승차 30 -> violation, 이월=10.
    report = capacity_violation_report(_route_hourly(), _route_schedule(), bus_capacity=2.0)

    route_150 = report[report["노선번호"] == "150"].iloc[0]
    assert bool(route_150["위반"]) is True
    assert route_150["이월"] == pytest.approx(10.0)


def test_capacity_violation_rate_is_fraction_of_rows_violating() -> None:
    # Only route 150 violates at bus_capacity=2 (수송능력=20<30); route 402's
    # 수송능력=(60/10)*2=12 < 20 also violates -- both rows violate here.
    rate = capacity_violation_rate(_route_hourly(), _route_schedule(), bus_capacity=2.0)
    assert rate == pytest.approx(1.0)

    rate_ok = capacity_violation_rate(_route_hourly(), _route_schedule(), bus_capacity=46.0)
    assert rate_ok == pytest.approx(0.0)


def test_capacity_violation_rate_rejects_empty() -> None:
    empty = pd.DataFrame(columns=["표준버스정류장ID", "정류장명", "노선번호", "시간대", "승차"])
    with pytest.raises(ValueError, match="empty"):
        capacity_violation_rate(empty, _route_schedule())


def test_capacity_violation_missing_headway_falls_back_to_median() -> None:
    # "999" has no schedule row -- falls back to the median headway among
    # the *other rows present in route_hourly* for the same stop/hour (150:
    # 6, 402: 10 -> median 8 -> 수송능력 = (60/8)*46 = 345). The fallback
    # can only draw from routes that actually show up in route_hourly, so
    # 150 and 402 must be included here too, not just 999.
    hourly = pd.concat(
        [
            _route_hourly(),
            pd.DataFrame(
                {
                    "표준버스정류장ID": [STOP],
                    "정류장명": ["종로2가"],
                    "노선번호": ["999"],
                    "시간대": [18],
                    "승차": [30.0],
                }
            ),
        ],
        ignore_index=True,
    )
    report = capacity_violation_report(hourly, _route_schedule(), bus_capacity=46.0)

    route_999 = report[report["노선번호"] == "999"].iloc[0]
    assert route_999["수송능력"] == pytest.approx(345.0)


def test_capacity_violation_filters_by_day_type() -> None:
    schedule = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP],
            "노선번호": ["150"],
            "요일유형": ["토요일"],
            "배차간격": [20.0],
            "배차정보없음": [False],
        }
    )
    hourly = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP],
            "정류장명": ["종로2가"],
            "노선번호": ["150"],
            "시간대": [18],
            "승차": [30.0],
        }
    )
    # Only a 토요일 schedule row exists for this route -- requesting
    # day_type="토요일" picks up its 20-minute headway.
    saturday = capacity_violation_report(hourly, schedule, day_type="토요일", bus_capacity=46.0)
    assert saturday.iloc[0]["수송능력"] == pytest.approx((60 / 20) * 46.0)


def test_capacity_violation_no_schedule_data_on_any_route_raises() -> None:
    # Neither route serving STOP has a matching schedule row -- same guard
    # as estimate_wait() (issue #109), reached here via the shared
    # fill_missing_headway().
    hourly = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP, STOP],
            "정류장명": ["종로2가", "종로2가"],
            "노선번호": ["777", "888"],
            "시간대": [18, 18],
            "승차": [30.0, 20.0],
        }
    )
    empty_schedule = _route_schedule().iloc[0:0]

    with pytest.raises(ValueError, match=str(STOP)):
        capacity_violation_report(hourly, empty_schedule)


def test_build_validation_report_aggregates_both_metrics() -> None:
    summary = build_validation_report(_wait_df(), _route_hourly(), _route_schedule())

    assert summary["비음수_위반율"] == pytest.approx(4 / 6)
    assert summary["용량_위반율"] == pytest.approx(0.0)
