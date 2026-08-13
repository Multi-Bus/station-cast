"""SciPy-based constrained refinement of transfer_rate and lambda (S2, issue #11).

Takes features/calibration.py's (issue #9) closed-form transfer_rate and
lambda estimates as both the optimizer's starting point and a
regularization anchor, then nudges them with scipy.optimize.minimize to
further reduce non-negativity violations and day-end closure residual.

Why anchor instead of a free search (lesson from an earlier discarded
attempt at this issue): starting from an ungrounded initial guess with no
penalty for drifting away let the optimizer "cheat" -- it satisfied the
day-end condition by artificially crashing late-hour demand while
inflating midday W into the tens of thousands, since nothing in the loss
function penalized a large positive W. Anchoring to #9's estimates (which
are themselves derived from observed boarding/alighting correlation, not
an arbitrary guess) means any large deviation must be justified by a real
reduction in constraint violation, not just found because it happened to
be unpenalized.

Because the anchor is #9's own output, this refinement cannot by itself
validate whether #9's scale is realistic -- it can only clean up the
remaining non-negativity/day-end violations without repeating the old
blow-up. Whether the *scale* (e.g. a several-hundred-person peak wait) is
plausible is a separate, open question. If this refinement leaves the
peak essentially unchanged, that is evidence the scale question is not an
optimizer artifact and needs an independent check (capacity), not more
tuning here.

Priority order follows 개발계획_최종.md §8's mitigation order for when not
all physical constraints can be simultaneously satisfied: 마감조건(day-end)
> 용량(capacity, not implemented here -- requires vehicle-seat and
route-topology data this project does not currently have) > 비음수
(non-negativity). DAY_END_WEIGHT > DEFAULT_VIOLATION_WEIGHT reflects that
ordering.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from stationcast.estimator.queue_balance import compute_wait_series
from stationcast.features.calibration import calibrate_corridor
from stationcast.validate.physical_constraints import build_validation_report

DAY_END_WEIGHT = 2.0
DEFAULT_VIOLATION_WEIGHT = 1.0
DEFAULT_REG_WEIGHT = 0.1

StopFrame = tuple[int, str, pd.Series, pd.Series]


def _stop_frames(hourly: pd.DataFrame) -> list[StopFrame]:
    """Split corridor_hourly-shaped data into one (id, name, boarding, alighting) per stop.

    Each stop's boarding/alighting series is indexed by 시간대 (hour), sorted ascending.
    """
    frames = []
    for stop_id, group in hourly.groupby("표준버스정류장ID", sort=False):
        ordered = group.sort_values("시간대").set_index("시간대")
        name = str(ordered["정류장명"].iloc[0])
        frames.append((int(stop_id), name, ordered["승차"], ordered["하차"]))
    return frames


def _unpack(params: np.ndarray, n_stops: int, n_hours: int) -> tuple[np.ndarray, np.ndarray]:
    """Split the flat optimizer vector into transfer_rate(n_stops) and lambda(n_stops, n_hours)."""
    transfer_rate = params[:n_stops]
    lam = params[n_stops:].reshape(n_stops, n_hours)
    return transfer_rate, lam


def _objective(
    params: np.ndarray,
    stop_frames: list[StopFrame],
    n_hours: int,
    prior_transfer: np.ndarray,
    prior_lambda: np.ndarray,
    violation_weight: float,
    day_end_weight: float,
    reg_weight: float,
) -> float:
    """Weighted day-end residual + non-negativity penalty + drift-from-#9 penalty."""
    n_stops = len(stop_frames)
    transfer_rate, lam = _unpack(params, n_stops, n_hours)

    total = 0.0
    for i, (_stop_id, _name, boarding, alighting) in enumerate(stop_frames):
        arrival_rate = pd.Series(lam[i], index=boarding.index)
        wait = compute_wait_series(
            boarding, alighting, transfer_rate=transfer_rate[i], arrival_rate=arrival_rate
        )
        day_end_residual = float(wait.iloc[-1]) ** 2
        violation_penalty = float(np.sum(np.minimum(wait.to_numpy(), 0.0) ** 2))
        total += day_end_weight * day_end_residual + violation_weight * violation_penalty

    drift = float(np.sum((transfer_rate - prior_transfer) ** 2)) + float(
        np.sum((lam - prior_lambda) ** 2)
    )
    total += reg_weight * drift

    return total


def calibrate_corridor_scipy(
    hourly: pd.DataFrame,
    violation_weight: float = DEFAULT_VIOLATION_WEIGHT,
    day_end_weight: float = DAY_END_WEIGHT,
    reg_weight: float = DEFAULT_REG_WEIGHT,
) -> dict[str, pd.DataFrame]:
    """Refine #9's transfer_rate/lambda with SciPy, anchored to those priors.

    Returns:
        "stops": 표준버스정류장ID, 정류장명, 환승률
        "lambda": 표준버스정류장ID, 정류장명, 시간대, lambda

    Same column names as features/calibration.calibrate_corridor()'s output,
    so both can be passed interchangeably to apply_scipy_calibration().
    """
    stop_frames = _stop_frames(hourly)
    n_stops = len(stop_frames)
    hours = sorted(hourly["시간대"].unique())
    n_hours = len(hours)
    stop_order = [stop_id for stop_id, *_ in stop_frames]

    prior_params, prior_lambdas = calibrate_corridor(hourly)
    prior_params = prior_params.set_index("표준버스정류장ID").loc[stop_order].reset_index()
    prior_transfer = prior_params["환승률"].to_numpy()

    prior_lambda = np.zeros((n_stops, n_hours))
    for i, stop_id in enumerate(stop_order):
        prior_lambda[i] = (
            prior_lambdas[prior_lambdas["표준버스정류장ID"] == stop_id]
            .sort_values("시간대")["lambda"]
            .to_numpy()
        )

    x0 = np.concatenate([prior_transfer, prior_lambda.ravel()])
    bounds = [(0.0, 1.0)] * n_stops + [(0.0, None)] * (n_stops * n_hours)

    result = minimize(
        _objective,
        x0,
        args=(
            stop_frames,
            n_hours,
            prior_transfer,
            prior_lambda,
            violation_weight,
            day_end_weight,
            reg_weight,
        ),
        method="L-BFGS-B",
        bounds=bounds,
    )

    transfer_rate, lam = _unpack(result.x, n_stops, n_hours)
    names = [name for _, name, *_ in stop_frames]

    stops_df = pd.DataFrame(
        {"표준버스정류장ID": stop_order, "정류장명": names, "환승률": transfer_rate}
    )
    lambda_df = pd.concat(
        [
            pd.DataFrame(
                {
                    "표준버스정류장ID": stop_order[i],
                    "정류장명": names[i],
                    "시간대": hours,
                    "lambda": lam[i],
                }
            )
            for i in range(n_stops)
        ],
        ignore_index=True,
    )

    return {"stops": stops_df, "lambda": lambda_df}


def apply_scipy_calibration(
    hourly: pd.DataFrame, stops_df: pd.DataFrame, lambda_df: pd.DataFrame
) -> pd.DataFrame:
    """Recompute W(s,t) for the whole corridor using the given per-stop parameters.

    stops_df/lambda_df schema matches both this module's own output and
    features/calibration.calibrate_corridor()'s output, so this doubles as
    the "before" computation (pass #9's raw priors) and the "after"
    computation (pass this module's refined result).
    """
    frames = []
    for stop_id, name, boarding, alighting in _stop_frames(hourly):
        transfer_rate = float(
            stops_df.loc[stops_df["표준버스정류장ID"] == stop_id, "환승률"].iloc[0]
        )
        lam = (
            lambda_df[lambda_df["표준버스정류장ID"] == stop_id]
            .sort_values("시간대")
            .set_index("시간대")["lambda"]
        )
        wait = compute_wait_series(
            boarding,
            alighting,
            transfer_rate=transfer_rate,
            arrival_rate=lam.loc[boarding.index],
        )
        frames.append(
            pd.DataFrame(
                {
                    "표준버스정류장ID": stop_id,
                    "정류장명": name,
                    "시간대": boarding.index,
                    "W": wait.to_numpy(),
                }
            )
        )

    return (
        pd.concat(frames, ignore_index=True)
        .sort_values(["표준버스정류장ID", "시간대"])
        .reset_index(drop=True)
    )


def run(hourly_path: Path, out_dir: Path) -> None:
    """Refine #9's calibration on corridor_hourly.parquet; write params + resulting W(s,t)."""
    hourly = pd.read_parquet(hourly_path)

    prior_params, prior_lambdas = calibrate_corridor(hourly)
    baseline_wait = apply_scipy_calibration(hourly, prior_params, prior_lambdas)
    before = build_validation_report(baseline_wait)

    calibration = calibrate_corridor_scipy(hourly)
    wait_refined = apply_scipy_calibration(hourly, calibration["stops"], calibration["lambda"])
    after = build_validation_report(wait_refined)

    out_dir.mkdir(parents=True, exist_ok=True)
    calibration["stops"].to_parquet(out_dir / "scipy_calibrated_stops.parquet", index=False)
    calibration["lambda"].to_parquet(out_dir / "scipy_calibrated_lambda.parquet", index=False)
    wait_refined.to_parquet(out_dir / "corridor_wait_scipy.parquet", index=False)

    print(
        f"#9 기준 — 비음수 위반율: {before['비음수_위반율']:.1%}, "
        f"일마감 평균 잔차: {before['일마감_평균잔차']:,.1f}"
    )
    print(
        f"SciPy 정교화 후 — 비음수 위반율: {after['비음수_위반율']:.1%}, "
        f"일마감 평균 잔차: {after['일마감_평균잔차']:,.1f}"
    )


if __name__ == "__main__":
    run(Path("data/processed/corridor_hourly.parquet"), Path("data/processed"))
