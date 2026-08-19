"""Tests for the per-route wait-population estimator (Little's Law)."""

import math

import pandas as pd
import pytest

from stationcast.estimator.wait_population import estimate_wait

STOP = 100000389


def _route_hourly() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "표준버스정류장ID": [STOP, STOP, STOP],
            "정류장명": ["종로2가", "종로2가", "종로2가"],
            "노선번호": ["150", "402", "150"],
            "시간대": [8, 8, 9],
            "승차": [30.0, 20.0, 12.0],
        }
    )


def _route_schedule() -> pd.DataFrame:
    # 최소배차 == 최대배차 == 배차간격 (zero registered range) -> cv=0 for
    # every route here, so these fixtures exercise only the headway math,
    # same as before cv_r was derived from the registered range.
    return pd.DataFrame(
        {
            "표준버스정류장ID": [STOP, STOP],
            "노선번호": ["150", "402"],
            "요일유형": ["평일", "평일"],
            "배차간격": [6.0, 10.0],
            "최소배차": [6.0, 10.0],
            "최대배차": [6.0, 10.0],
            "배차정보없음": [False, False],
        }
    )


def test_single_route_matches_littles_law_by_hand() -> None:
    # route 150 alone, hour 9: B=12, headway=6 -> wait=3min -> W = 12*3/60 = 0.6
    hourly = _route_hourly()[_route_hourly()["시간대"] == 9]
    result = estimate_wait(hourly, _route_schedule())

    assert result.iloc[0]["W"] == pytest.approx(0.6)


def test_multiple_routes_at_same_stop_hour_sum() -> None:
    # hour 8: route 150 (B=30, headway=6 -> 30*3/60=1.5) +
    # route 402 (B=20, headway=10 -> 20*5/60=1.6667)
    result = estimate_wait(_route_hourly(), _route_schedule())

    hour8 = result[result["시간대"] == 8].iloc[0]
    assert hour8["W"] == pytest.approx(1.5 + 20 * 5 / 60)


def test_result_is_never_negative() -> None:
    result = estimate_wait(_route_hourly(), _route_schedule())

    assert (result["W"] >= 0).all()


def test_wider_registered_headway_range_scales_wait_by_one_plus_cv_squared() -> None:
    # route 150, headway 6, registered range [2, 10] -> a wider range than
    # the zero-range baseline means cv_r > 0, so wait should exceed the
    # plain headway/2 estimate by the (1 + cv_r**2) factor.
    baseline_schedule = _route_schedule()
    irregular_schedule = baseline_schedule.copy()
    irregular_schedule.loc[irregular_schedule["노선번호"] == "150", ["최소배차", "최대배차"]] = [
        2.0,
        10.0,
    ]

    hourly = _route_hourly()[
        (_route_hourly()["시간대"] == 9) & (_route_hourly()["노선번호"] == "150")
    ]
    baseline = estimate_wait(hourly, baseline_schedule)
    irregular = estimate_wait(hourly, irregular_schedule)

    cv = ((10.0 - 2.0) / math.sqrt(12)) / 6.0
    expected = baseline.iloc[0]["W"] * (1 + cv**2)
    assert irregular.iloc[0]["W"] == pytest.approx(expected)


def test_missing_headway_falls_back_to_median_of_other_routes_at_stop() -> None:
    hourly = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP, STOP, STOP],
            "정류장명": ["종로2가", "종로2가", "종로2가"],
            "노선번호": ["150", "402", "999"],
            "시간대": [8, 8, 8],
            "승차": [30.0, 20.0, 10.0],
        }
    )
    # "999" has no schedule row at all -- falls back to the median of 150
    # (6) and 402 (10), i.e. 8.
    result = estimate_wait(hourly, _route_schedule())

    route_999_wait = 10.0 * (8.0 / 2) / 60
    expected_total = (30 * 3 / 60) + (20 * 5 / 60) + route_999_wait
    assert result.iloc[0]["W"] == pytest.approx(expected_total)


def test_flagged_no_schedule_route_also_falls_back_to_median() -> None:
    hourly = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP, STOP],
            "정류장명": ["종로2가", "종로2가"],
            "노선번호": ["150", "402"],
            "시간대": [8, 8],
            "승차": [30.0, 20.0],
        }
    )
    schedule = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP, STOP],
            "노선번호": ["150", "402"],
            "요일유형": ["평일", "평일"],
            "배차간격": [6.0, 0.0],
            "최소배차": [6.0, 0.0],
            "최대배차": [6.0, 0.0],
            "배차정보없음": [False, True],
        }
    )
    # 402 is flagged 배차정보없음 despite having a 배차간격 value -- must be
    # treated as missing (median of the one remaining route, 150's 6).
    result = estimate_wait(hourly, schedule)

    expected_total = (30 * 3 / 60) + (20 * 3 / 60)
    assert result.iloc[0]["W"] == pytest.approx(expected_total)


def test_filters_by_day_type() -> None:
    schedule = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP, STOP],
            "노선번호": ["150", "150"],
            "요일유형": ["평일", "토요일"],
            "배차간격": [6.0, 20.0],
            "최소배차": [6.0, 20.0],
            "최대배차": [6.0, 20.0],
            "배차정보없음": [False, False],
        }
    )
    hourly = _route_hourly()[_route_hourly()["시간대"] == 9]

    weekday = estimate_wait(hourly, schedule, day_type="평일")
    saturday = estimate_wait(hourly, schedule, day_type="토요일")

    assert weekday.iloc[0]["W"] == pytest.approx(12 * 3 / 60)
    assert saturday.iloc[0]["W"] == pytest.approx(12 * 10 / 60)
