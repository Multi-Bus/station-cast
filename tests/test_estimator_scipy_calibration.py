"""Tests for SciPy-based refinement of #9's transfer_rate/lambda (issue #11)."""

import numpy as np
import pandas as pd
import pytest

from stationcast.estimator.scipy_calibration import (
    DAY_END_WEIGHT,
    DEFAULT_VIOLATION_WEIGHT,
    _objective,
    _stop_frames,
    _unpack,
    apply_scipy_calibration,
    calibrate_corridor_scipy,
)
from stationcast.features.calibration import calibrate_corridor


def test_unpack_splits_params_correctly() -> None:
    # n_stops=2, n_hours=3: transfer_rate(2*3=6) + lambda(2*3=6)
    params = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0])

    transfer_rate, lam = _unpack(params, n_stops=2, n_hours=3)

    assert transfer_rate.tolist() == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert lam.tolist() == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]


def test_objective_hand_computed_no_violation() -> None:
    boarding = pd.Series([10.0, 5.0])
    alighting = pd.Series([20.0, 10.0])
    stop_frames = [(1, "A", boarding, alighting)]
    params = np.array([0.5, 0.5, 2.0, 2.0])  # transfer_rate=[0.5,0.5], lambda=[2,2]
    prior_transfer = np.array([[0.5, 0.5]])
    prior_lambda = np.array([[2.0, 2.0]])

    loss = _objective(
        params,
        stop_frames,
        n_hours=2,
        prior_transfer=prior_transfer,
        prior_lambda=prior_lambda,
        violation_weight=1.0,
        day_end_weight=1.0,
        reg_weight=1.0,
    )

    # W0 = 0 + 2 + 20*0.5 - 10 = 2; W1 = 2 + 2 + 10*0.5 - 5 = 4
    # day_end_residual = 4^2 = 16; both W>=0 so violation penalty = 0
    # params == prior, so drift = 0
    assert loss == pytest.approx(16.0)


def test_objective_penalizes_negative_wait() -> None:
    boarding = pd.Series([10.0, 5.0])
    alighting = pd.Series([0.0, 0.0])
    stop_frames = [(1, "A", boarding, alighting)]
    params = np.array([0.0, 0.0, 0.0, 0.0])  # transfer_rate=[0,0], lambda=[0,0]
    prior_transfer = np.array([[0.0, 0.0]])
    prior_lambda = np.array([[0.0, 0.0]])

    loss = _objective(
        params,
        stop_frames,
        n_hours=2,
        prior_transfer=prior_transfer,
        prior_lambda=prior_lambda,
        violation_weight=1.0,
        day_end_weight=1.0,
        reg_weight=1.0,
    )
    # W0=-10, W1=-15; day_end_residual=225; violation_penalty=100+225=325; drift=0
    assert loss == pytest.approx(550.0)

    loss_weighted = _objective(
        params,
        stop_frames,
        n_hours=2,
        prior_transfer=prior_transfer,
        prior_lambda=prior_lambda,
        violation_weight=2.0,
        day_end_weight=1.0,
        reg_weight=1.0,
    )
    assert loss_weighted == pytest.approx(225.0 + 2 * 325.0)


def test_objective_penalizes_drift_from_prior() -> None:
    boarding = pd.Series([10.0])
    alighting = pd.Series([10.0])
    stop_frames = [(1, "A", boarding, alighting)]
    params = np.array([0.3, 5.0])  # transfer_rate=0.3, lambda=[5.0]
    prior_transfer = np.array([0.0])
    prior_lambda = np.array([[0.0]])

    # zero out the constraint terms so only drift contributes
    loss = _objective(
        params,
        stop_frames,
        n_hours=1,
        prior_transfer=prior_transfer,
        prior_lambda=prior_lambda,
        violation_weight=0.0,
        day_end_weight=0.0,
        reg_weight=1.0,
    )
    # drift = (0.3-0.0)^2 + (5.0-0.0)^2 = 0.09 + 25.0
    assert loss == pytest.approx(0.09 + 25.0)


def test_objective_penalizes_capacity_violation() -> None:
    boarding = pd.Series([0.0, 0.0])
    # alighting nonzero (with transfer_rate=0, it still contributes nothing to W) so this
    # hour isn't read as "service closed" -- see compute_wait_series's zero-boarding-and-
    # zero-alighting reset.
    alighting = pd.Series([1.0, 1.0])
    stop_frames = [(1, "A", boarding, alighting)]
    params = np.array([0.0, 0.0, 10.0, 0.0])  # transfer_rate=[0,0], lambda=[10,0]
    prior_transfer = np.array([[0.0, 0.0]])
    prior_lambda = np.array([[10.0, 0.0]])

    # W0 = 10, W1 = 10 (no boarding to drain it); capacity=5 -> 5 over each hour
    loss = _objective(
        params,
        stop_frames,
        n_hours=2,
        prior_transfer=prior_transfer,
        prior_lambda=prior_lambda,
        violation_weight=0.0,
        day_end_weight=0.0,
        reg_weight=0.0,
        capacity=np.array([5.0]),
        capacity_weight=2.0,
    )
    assert loss == pytest.approx(2.0 * (5.0**2 + 5.0**2))


def test_objective_skips_capacity_penalty_when_capacity_is_none() -> None:
    boarding = pd.Series([0.0])
    alighting = pd.Series([0.0])
    stop_frames = [(1, "A", boarding, alighting)]
    params = np.array([0.0, 1000.0])  # transfer_rate=[0], lambda=[1000] -- way over any capacity
    prior_transfer = np.array([[0.0]])
    prior_lambda = np.array([[1000.0]])

    loss = _objective(
        params,
        stop_frames,
        n_hours=1,
        prior_transfer=prior_transfer,
        prior_lambda=prior_lambda,
        violation_weight=0.0,
        day_end_weight=0.0,
        reg_weight=0.0,
    )
    assert loss == 0.0


def test_stop_frames_splits_and_sorts_by_hour() -> None:
    hourly = pd.DataFrame(
        {
            "표준버스정류장ID": [2, 2, 1, 1],
            "정류장명": ["B", "B", "A", "A"],
            "시간대": [1, 0, 1, 0],
            "승차": [5, 10, 3, 4],
            "하차": [1, 2, 1, 1],
        }
    )

    frames = _stop_frames(hourly)
    ids = [stop_id for stop_id, *_ in frames]
    assert set(ids) == {1, 2}

    stop1 = next(f for f in frames if f[0] == 1)
    assert stop1[1] == "A"
    assert stop1[2].tolist() == [4, 3]  # boarding, sorted by hour 0,1
    assert list(stop1[2].index) == [0, 1]


def _synthetic_hourly() -> pd.DataFrame:
    # 2 stops, 4 hours each -- small enough for a fast optimize() call in tests.
    return pd.DataFrame(
        {
            "표준버스정류장ID": [1, 1, 1, 1, 2, 2, 2, 2],
            "정류장명": ["A", "A", "A", "A", "B", "B", "B", "B"],
            "시간대": [0, 1, 2, 3, 0, 1, 2, 3],
            "승차": [10, 8, 6, 4, 20, 15, 10, 5],
            "하차": [2, 3, 4, 20, 5, 5, 5, 30],
        }
    )


def test_calibrate_corridor_scipy_respects_bounds() -> None:
    result = calibrate_corridor_scipy(_synthetic_hourly())

    stops = result["stops"]
    assert set(stops["표준버스정류장ID"]) == {1, 2}
    assert (stops["환승률"] >= 0).all()
    assert (stops["환승률"] <= 1).all()

    lam = result["lambda"]
    assert (lam["lambda"] >= 0).all()


def test_calibrate_corridor_scipy_stays_close_to_prior_with_high_reg_weight() -> None:
    hourly = _synthetic_hourly()
    prior_params, prior_lambdas = calibrate_corridor(hourly)

    result = calibrate_corridor_scipy(hourly, reg_weight=1e6)

    merged = result["stops"].merge(
        prior_params, on="표준버스정류장ID", suffixes=("_refined", "_prior")
    )
    assert merged["환승률_refined"].to_numpy() == pytest.approx(
        merged["환승률_prior"].to_numpy(), abs=1e-2
    )

    lam_merged = result["lambda"].merge(
        prior_lambdas, on=["표준버스정류장ID", "시간대"], suffixes=("_refined", "_prior")
    )
    assert lam_merged["lambda_refined"].to_numpy() == pytest.approx(
        lam_merged["lambda_prior"].to_numpy(), abs=1e-1
    )


def test_calibrate_corridor_scipy_reduces_violation_loss_from_prior_baseline() -> None:
    hourly = _synthetic_hourly()
    stop_frames = _stop_frames(hourly)
    n_hours = 4

    prior_params, prior_lambdas = calibrate_corridor(hourly)
    stop_order = [stop_id for stop_id, *_ in stop_frames]
    prior_params = prior_params.set_index("표준버스정류장ID").loc[stop_order].reset_index()
    prior_transfer_scalar = prior_params["환승률"].to_numpy()
    prior_transfer = np.tile(prior_transfer_scalar[:, None], (1, n_hours))
    prior_lambda = np.array(
        [
            prior_lambdas[prior_lambdas["표준버스정류장ID"] == sid]
            .sort_values("시간대")["lambda"]
            .to_numpy()
            for sid in stop_order
        ]
    )
    x0 = np.concatenate([prior_transfer.ravel(), prior_lambda.ravel()])

    prior_loss = _objective(
        x0,
        stop_frames,
        n_hours,
        prior_transfer,
        prior_lambda,
        DEFAULT_VIOLATION_WEIGHT,
        DAY_END_WEIGHT,
        reg_weight=0.0,
    )

    # reg_weight=0 here too, so this is an apples-to-apples free optimization
    # over the same reg_weight=0 objective just evaluated above at x0.
    result = calibrate_corridor_scipy(hourly, reg_weight=0.0)
    refined_params = np.concatenate(
        [
            result["stops"].sort_values(["표준버스정류장ID", "시간대"])["환승률"].to_numpy(),
            result["lambda"]
            .sort_values(["표준버스정류장ID", "시간대"])["lambda"]
            .to_numpy(),
        ]
    )
    refined_loss = _objective(
        refined_params,
        stop_frames,
        n_hours,
        prior_transfer,
        prior_lambda,
        DEFAULT_VIOLATION_WEIGHT,
        DAY_END_WEIGHT,
        reg_weight=0.0,
    )

    assert refined_loss <= prior_loss + 1e-6


def test_apply_scipy_calibration_uses_per_stop_params() -> None:
    hourly = _synthetic_hourly()
    stops_df = pd.DataFrame(
        {
            "표준버스정류장ID": [1, 2],
            "정류장명": ["A", "B"],
            "환승률": [0.5, 0.2],
        }
    )
    lambda_df = pd.DataFrame(
        {
            "표준버스정류장ID": [1, 1, 1, 1, 2, 2, 2, 2],
            "정류장명": ["A", "A", "A", "A", "B", "B", "B", "B"],
            "시간대": [0, 1, 2, 3, 0, 1, 2, 3],
            "lambda": [3.0, 3.0, 3.0, 3.0, 1.0, 1.0, 1.0, 1.0],
        }
    )

    result = apply_scipy_calibration(hourly, stops_df, lambda_df)

    assert list(result.columns) == ["표준버스정류장ID", "정류장명", "시간대", "W"]
    assert len(result) == 8

    # Stop 1, hour 0: boarding=10, alighting=2, transfer_rate=0.5, lambda=3
    # W0 = 0 + 3 + 2*0.5 - 10 = -6
    stop1_hour0 = result[
        (result["표준버스정류장ID"] == 1) & (result["시간대"] == 0)
    ]["W"].iloc[0]
    assert stop1_hour0 == pytest.approx(-6.0)


def test_apply_scipy_calibration_uses_per_hour_transfer_rate_when_present() -> None:
    """A 시간대 column in stops_df selects the per-hour path (this module's own output)."""
    hourly = _synthetic_hourly()
    stops_df = pd.DataFrame(
        {
            "표준버스정류장ID": [1, 1, 1, 1, 2, 2, 2, 2],
            "정류장명": ["A", "A", "A", "A", "B", "B", "B", "B"],
            "시간대": [0, 1, 2, 3, 0, 1, 2, 3],
            "환승률": [0.9, 0.1, 0.1, 0.1, 0.2, 0.2, 0.2, 0.2],
        }
    )
    lambda_df = pd.DataFrame(
        {
            "표준버스정류장ID": [1, 1, 1, 1, 2, 2, 2, 2],
            "정류장명": ["A", "A", "A", "A", "B", "B", "B", "B"],
            "시간대": [0, 1, 2, 3, 0, 1, 2, 3],
            "lambda": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        }
    )

    result = apply_scipy_calibration(hourly, stops_df, lambda_df)

    # Stop 1, hour 0: boarding=10, alighting=2, transfer_rate=0.9, lambda=0
    # W0 = 0 + 0 + 2*0.9 - 10 = -8.2
    stop1_hour0 = result[
        (result["표준버스정류장ID"] == 1) & (result["시간대"] == 0)
    ]["W"].iloc[0]
    assert stop1_hour0 == pytest.approx(-8.2)

    # Stop 1, hour 1: boarding=8, alighting=3, transfer_rate=0.1 (a different, lower rate this hour)
    # W1 = -8.2 + 0 + 3*0.1 - 8 = -15.9
    stop1_hour1 = result[
        (result["표준버스정류장ID"] == 1) & (result["시간대"] == 1)
    ]["W"].iloc[0]
    assert stop1_hour1 == pytest.approx(-15.9)
