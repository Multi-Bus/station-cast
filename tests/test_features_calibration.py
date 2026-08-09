"""Tests for transfer rate estimation and lambda calibration (issue #9)."""

import pandas as pd
import pytest

from stationcast.features.calibration import (
    calibrate_corridor,
    calibrate_lambda,
    estimate_transfer_lag,
    estimate_transfer_rate,
)


def test_estimate_transfer_lag_finds_the_correct_lag() -> None:
    alighting = pd.Series([5, 20, 8, 25, 3])
    # boarding(t) = 0.5 * alighting(t-2) for t >= 2; boarding[0:2] is noise
    # unrelated to nearby alighting values, so lag=2 should win cleanly.
    boarding = pd.Series([100, 100, 2.5, 10, 4])

    assert estimate_transfer_lag(boarding, alighting) == 2


def test_estimate_transfer_rate_recovers_known_rate() -> None:
    alighting = pd.Series([5, 20, 8, 25, 3])
    boarding = pd.Series([100, 100, 2.5, 10, 4])

    rate = estimate_transfer_rate(boarding, alighting, lag=2)

    assert rate == pytest.approx(0.5)


def test_estimate_transfer_rate_clips_to_valid_range() -> None:
    alighting = pd.Series([1.0, 2.0, 3.0])
    boarding = pd.Series([5.0, 10.0, 15.0])  # true slope is 5x

    rate = estimate_transfer_rate(boarding, alighting, lag=0)

    assert rate == 1.0


def test_estimate_transfer_rate_feasibility_ceiling_resists_outlier_hour() -> None:
    # 5 hours with a true ratio of 0.3, plus 1 outlier hour (same alighting,
    # 10x the boarding) that would drag a plain OLS-through-origin slope up
    # to 0.75 -- the feasibility ceiling (10th percentile of hourly ratios)
    # should keep the estimate anchored to the consistent 0.3 pattern instead.
    alighting = pd.Series([10, 10, 10, 10, 10, 10])
    boarding = pd.Series([3, 3, 3, 3, 3, 30])

    rate = estimate_transfer_rate(boarding, alighting, lag=0)

    assert rate == pytest.approx(0.3)


def test_calibrate_lambda_hand_computed() -> None:
    boarding = pd.Series([10, 20, 30])  # total = 60
    alighting = pd.Series([5, 5, 5])  # total = 15
    # budget = 60 - 0.4*15 = 54; transfer_in = 0.4*5 = 2 each hour, so
    # residual demand = [8, 18, 28], which sums to 54 == budget -- so
    # lambda equals residual demand exactly (see the lag=1 test below for
    # why this equality always holds when nothing gets floor-clipped).
    expected = pd.Series([8.0, 18.0, 28.0], name="lambda")

    lam = calibrate_lambda(boarding, alighting, transfer_rate=0.4, lag=0)

    pd.testing.assert_series_equal(lam, expected)


def test_calibrate_lambda_clips_negative_budget_to_zero() -> None:
    boarding = pd.Series([1, 1, 1])  # total = 3
    alighting = pd.Series([100, 100, 100])  # total = 300
    # budget = 3 - 1.0*300 = negative -> clipped to 0

    lam = calibrate_lambda(boarding, alighting, transfer_rate=1.0, lag=0)

    assert (lam == 0).all()


def test_calibrate_lambda_excludes_alighting_past_the_lag_boundary() -> None:
    # the last `lag` hours' alighting can't transfer within the same day (it
    # would board tomorrow), so it must be excluded from the budget calc --
    # if it weren't, this stop's huge final-hour alighting would sink the
    # budget to zero.
    boarding = pd.Series([10, 10, 10, 10])
    alighting = pd.Series([1, 1, 1, 1000])

    lam = calibrate_lambda(boarding, alighting, transfer_rate=0.5, lag=1)

    # budget = 40 - 0.5*(1+1+1) = 38.5; transfer_in = [0, 0.5, 0.5, 0.5];
    # residual demand = [10, 9.5, 9.5, 9.5], which sums to 38.5 == budget.
    expected = pd.Series([10.0, 9.5, 9.5, 9.5], name="lambda")
    pd.testing.assert_series_equal(lam, expected)


def test_calibrate_corridor_shapes_and_columns() -> None:
    hourly = pd.DataFrame(
        {
            "표준버스정류장ID": [1, 1, 1, 2, 2, 2],
            "정류장명": ["A", "A", "A", "B", "B", "B"],
            "시간대": [0, 1, 2, 0, 1, 2],
            "승차": [10, 20, 30, 5, 10, 15],
            "하차": [5, 5, 5, 2, 2, 2],
        }
    )

    params, lambdas = calibrate_corridor(hourly)

    assert list(params["표준버스정류장ID"]) == [1, 2]
    assert set(params.columns) == {"표준버스정류장ID", "정류장명", "환승_시차", "환승률"}
    assert len(lambdas) == 6
    assert set(lambdas.columns) == {"표준버스정류장ID", "정류장명", "시간대", "lambda"}
    assert (lambdas["lambda"] >= 0).all()
