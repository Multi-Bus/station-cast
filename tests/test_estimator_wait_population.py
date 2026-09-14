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
            "유형": ["간선", "간선"],
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
            "유형": ["간선", "간선"],
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


OTHER_STOP = 100000390


def test_lone_route_without_headway_falls_back_to_its_유형_median() -> None:
    # OTHER_STOP is served by one route ("777") with no headway, so there is
    # no sibling route at that stop to borrow from -- the case that breaks
    # 서울 전체 (125 stops, 117 of them single-route). It is 간선, and the
    # only other 간선 route here is "150" at 6분, so 777 takes 6분:
    # W = 30 * (6/2) / 60 = 1.5.
    hourly = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP, OTHER_STOP],
            "정류장명": ["종로2가", "종로3가"],
            "노선번호": ["150", "777"],
            "시간대": [8, 8],
            "승차": [30.0, 30.0],
        }
    )
    schedule = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP, OTHER_STOP],
            "노선번호": ["150", "777"],
            "유형": ["간선", "간선"],
            "요일유형": ["평일", "평일"],
            "배차간격": [6.0, None],
            "최소배차": [6.0, None],
            "최대배차": [6.0, None],
            "배차정보없음": [False, True],
        }
    )

    result = estimate_wait(hourly, schedule)

    assert result[result["표준버스정류장ID"] == OTHER_STOP].iloc[0]["W"] == pytest.approx(1.5)


def test_유형_median_is_per_route_not_per_stop_hour_row() -> None:
    # "150" serves two stops and "402" one, but both are 간선 with equal
    # weight in the median: median(6, 10) = 8, not 6 (which is what
    # weighting by 150's two rows would give). 777 borrows 8분 ->
    # W = 30 * 4 / 60 = 2.0.
    hourly = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP, OTHER_STOP, STOP, 100000391],
            "정류장명": ["종로2가", "종로3가", "종로2가", "종로4가"],
            "노선번호": ["150", "150", "402", "777"],
            "시간대": [8, 8, 8, 8],
            "승차": [1.0, 1.0, 1.0, 30.0],
        }
    )
    schedule = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP, OTHER_STOP, STOP, 100000391],
            "노선번호": ["150", "150", "402", "777"],
            "유형": ["간선", "간선", "간선", "간선"],
            "요일유형": ["평일"] * 4,
            "배차간격": [6.0, 6.0, 10.0, None],
            "최소배차": [6.0, 6.0, 10.0, None],
            "최대배차": [6.0, 6.0, 10.0, None],
            "배차정보없음": [False, False, False, True],
        }
    )

    result = estimate_wait(hourly, schedule)

    assert result[result["표준버스정류장ID"] == 100000391].iloc[0]["W"] == pytest.approx(2.0)


def test_route_missing_from_the_schedule_file_entirely_is_dropped() -> None:
    # No schedule row at all means no 유형 either, so there is no group to
    # borrow a median from -- 8 서울 routes are in this state (they are
    # absent from 서울시버스노선기본정보). Those rows are dropped rather
    # than raising, and a stop served only by such routes drops out.
    hourly = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP, STOP],
            "정류장명": ["종로2가", "종로2가"],
            "노선번호": ["777", "888"],
            "시간대": [8, 8],
            "승차": [30.0, 20.0],
        }
    )
    empty_schedule = _route_schedule().iloc[0:0]

    result = estimate_wait(hourly, empty_schedule)

    assert result.empty


def test_known_유형_with_no_headway_anywhere_raises_instead_of_nan() -> None:
    # "777" has a 유형, so it is not the dropped-route case -- but no 간선
    # route anywhere in this input has a headway, so the second-level median
    # is undefined too. Should raise, not silently produce a NaN W
    # (issue #109: a fully-missing stop used to pass through as NaN).
    hourly = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP],
            "정류장명": ["종로2가"],
            "노선번호": ["777"],
            "시간대": [8],
            "승차": [30.0],
        }
    )
    schedule = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP],
            "노선번호": ["777"],
            "유형": ["간선"],
            "요일유형": ["평일"],
            "배차간격": [None],
            "최소배차": [None],
            "최대배차": [None],
            "배차정보없음": [True],
        }
    )

    with pytest.raises(ValueError, match=str(STOP)):
        estimate_wait(hourly, schedule)


def test_filters_by_day_type() -> None:
    schedule = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP, STOP],
            "노선번호": ["150", "150"],
            "유형": ["간선", "간선"],
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


def _factors() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "표준버스정류장ID": [STOP],
            "보정계수_승차_정규화_주말+공휴일_강수_저온": [1.4],
        }
    )


def test_factors_scale_w_by_the_groups_normalized_factor() -> None:
    hourly = _route_hourly()[_route_hourly()["시간대"] == 9]
    labels = ("주말+공휴일", "강수", "저온")

    base = estimate_wait(hourly, _route_schedule())
    corrected = estimate_wait(hourly, _route_schedule(), factors=_factors(), labels=labels)

    assert corrected.iloc[0]["W"] == pytest.approx(base.iloc[0]["W"] * 1.4)


def test_omitting_factors_reproduces_the_uncorrected_estimate() -> None:
    result = estimate_wait(_route_hourly(), _route_schedule())
    explicit_none = estimate_wait(_route_hourly(), _route_schedule(), factors=None, labels=None)

    pd.testing.assert_frame_equal(result, explicit_none)


def test_stop_missing_from_the_factor_table_keeps_its_uncorrected_boarding() -> None:
    # A left join miss must not NaN out the stop's W -- the correction is an
    # adjustment, not a precondition for having an estimate at all.
    hourly = _route_hourly()[_route_hourly()["시간대"] == 9]
    other_stop = _factors().assign(표준버스정류장ID=[999999999])

    result = estimate_wait(
        hourly, _route_schedule(), factors=other_stop, labels=("주말+공휴일", "강수", "저온")
    )

    assert result.iloc[0]["W"] == pytest.approx(0.6)


def test_factors_without_labels_is_rejected() -> None:
    with pytest.raises(ValueError, match="together"):
        estimate_wait(_route_hourly(), _route_schedule(), factors=_factors())
