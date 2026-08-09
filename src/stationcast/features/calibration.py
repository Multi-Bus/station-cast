"""Transfer rate estimation and lambda (new-arrival rate) calibration (S2, issue #9).

Two of the three components of the queue balance equation's inflow are
estimated here, per the plan (개발계획_최종.md §2.3, §8):

- transfer_rate(s): estimated from the lagged correlation between a stop's
  alighting and boarding time series -- the plan's own risk mitigation for
  when transfer rate can't be measured directly ("하차<->승차 시차 상관으로 추정").
- lambda(s,t): the remaining new-arrival budget needed to satisfy the
  day-end closure constraint (W(s,23) ~= 0), distributed across hours in
  proportion to that hour's boarding left unexplained by transfers.

This is a closed-form heuristic, not the formal SciPy constrained
optimization in estimator/ (issue #11). It replaces the S1 placeholders
(transfer_rate=0.3, arrival_rate=0) in compute_wait_series() with real
per-stop estimates; issue #11 can refine these further.
"""

from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd

MAX_TRANSFER_LAG = 3
"""Search up to this many hours of delay between alighting and boarding
when looking for the best-correlated transfer lag."""

FEASIBILITY_PERCENTILE = 10
"""Percentile (of per-hour boarding/alighting ratios) used as a ceiling on
the fitted transfer rate. A plain OLS-through-origin slope on this corridor
(up to 61 overlapping routes per stop) is dominated by rush-hour boarding
that has nothing to do with transfers -- both alighting and boarding peak
together at the same hours for unrelated reasons, which inflates the slope
well past 1.0 for busy stops. Capping at a low percentile (rather than the
strict minimum, which collapses to whatever single hour is noisiest) rules
out that inflation while staying robust to one-off low-traffic hours."""


def estimate_transfer_lag(
    boarding: pd.Series, alighting: pd.Series, max_lag: int = MAX_TRANSFER_LAG
) -> int:
    """Pick the lag (hours) with the strongest alighting(t) vs boarding(t+lag) correlation.

    Only positive correlation makes physical sense here (more alighting should
    predict *more*, not less, later boarding), so lags with negative or
    undefined (zero-variance) correlation are never selected over one with
    positive correlation.
    """
    board = boarding.to_numpy(dtype="float64")
    alight = alighting.to_numpy(dtype="float64")

    best_lag = 0
    best_corr = -np.inf
    for lag in range(max_lag + 1):
        x = alight[: len(alight) - lag]
        y = board[lag:]
        if len(x) < 2 or np.std(x) == 0 or np.std(y) == 0:
            continue
        corr = np.corrcoef(x, y)[0, 1]
        if corr > best_corr:
            best_corr = corr
            best_lag = lag
    return best_lag


def estimate_transfer_rate(boarding: pd.Series, alighting: pd.Series, lag: int) -> float:
    """Estimate the transfer rate from boarding(t+lag) and alighting(t).

    Two candidate estimates are combined, and the smaller one wins:

    - An OLS slope through the origin (physically, transfer boarding is
      alighting times a rate, with no constant offset).
    - A feasibility ceiling: transfer-attributable boarding cannot exceed
      the hour's actual observed boarding, so the rate can't systematically
      exceed the FEASIBILITY_PERCENTILE of per-hour boarding/alighting
      ratios. This is what actually keeps the estimate honest -- the OLS
      slope alone is dominated by rush-hour co-movement that isn't really
      about transfers (see FEASIBILITY_PERCENTILE) and regularly comes out
      above 1.0 on this corridor.

    Finally clipped to [0, 1], since a transfer rate is a fraction.
    """
    board = boarding.to_numpy(dtype="float64")
    alight = alighting.to_numpy(dtype="float64")

    x = alight[: len(alight) - lag]
    y = board[lag:]

    denom = float(np.sum(x**2))
    if denom == 0:
        return 0.0
    slope = float(np.sum(x * y) / denom)

    nonzero = x > 0
    if nonzero.any():
        feasibility_ceiling = float(np.percentile(y[nonzero] / x[nonzero], FEASIBILITY_PERCENTILE))
    else:
        feasibility_ceiling = 1.0

    rate = min(slope, feasibility_ceiling)
    return min(max(rate, 0.0), 1.0)


def calibrate_lambda(
    boarding: pd.Series, alighting: pd.Series, transfer_rate: float, lag: int
) -> pd.Series:
    """Distribute the day-end-closure arrival budget by residual (non-transfer) demand.

    Total budget: derived from summing the queue balance recursion over the
    full day and requiring W(s,23) ~= 0: total new arrivals ~= total
    boarding - total transfer-in. The alighting total used here excludes the
    last ``lag`` hours -- their transfer boarding would fall after hour 23
    (i.e. tomorrow, outside today's data), so counting them would
    understate the budget.

    Per-hour weights: boarding(t) minus that hour's already-estimated
    transfer-in (transfer_rate * alighting(t - lag), zero before hour
    ``lag``), clipped at 0. Weighting by raw boarding would double-count
    transfer-heavy hours as if they were also new-arrival-heavy.

    Clipped at 0 overall -- a stop where transfers alone would already
    exceed boarding has no meaningful new-arrival budget under this
    heuristic; that is a real limitation, not something to silently paper
    over (see 개발계획_최종.md §8 risk register).
    """
    total_boarding = float(boarding.sum())
    if total_boarding == 0:
        return pd.Series(0.0, index=boarding.index, name="lambda")

    board = boarding.to_numpy(dtype="float64")
    alight = alighting.to_numpy(dtype="float64")

    valid_alighting_total = float(alight[: len(alight) - lag].sum())
    budget = max(total_boarding - transfer_rate * valid_alighting_total, 0.0)

    transfer_in = np.zeros_like(board)
    transfer_in[lag:] = transfer_rate * alight[: len(alight) - lag]
    residual_demand = np.clip(board - transfer_in, 0.0, None)

    total_residual = float(residual_demand.sum())
    if total_residual == 0:
        weights = np.full(len(board), 1.0 / len(board))
    else:
        weights = residual_demand / total_residual

    return pd.Series(weights * budget, index=boarding.index, name="lambda")


class StopCalibration(NamedTuple):
    transfer_lag: int
    transfer_rate: float
    lambda_series: pd.Series


def calibrate_stop(boarding: pd.Series, alighting: pd.Series) -> StopCalibration:
    """Estimate transfer lag/rate and the hourly lambda series for one stop."""
    lag = estimate_transfer_lag(boarding, alighting)
    transfer_rate = estimate_transfer_rate(boarding, alighting, lag)
    lam = calibrate_lambda(boarding, alighting, transfer_rate, lag)
    return StopCalibration(transfer_lag=lag, transfer_rate=transfer_rate, lambda_series=lam)


def calibrate_corridor(hourly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply calibration to every stop. Returns (params, lambda) DataFrames.

    ``hourly`` must have columns 표준버스정류장ID, 정류장명, 시간대, 승차, 하차
    (see data/README.md), matching corridor_hourly.parquet. Each stop is
    calibrated independently, same as the queue balance model itself.
    """
    param_rows = []
    lambda_frames = []

    for stop_id, group in hourly.groupby("표준버스정류장ID", sort=False):
        ordered = group.sort_values("시간대")
        stop_name = ordered["정류장명"].iloc[0]

        result = calibrate_stop(ordered["승차"], ordered["하차"])

        param_rows.append(
            {
                "표준버스정류장ID": stop_id,
                "정류장명": stop_name,
                "환승_시차": result.transfer_lag,
                "환승률": result.transfer_rate,
            }
        )

        lambda_df = ordered[["표준버스정류장ID", "정류장명", "시간대"]].copy()
        lambda_df["lambda"] = result.lambda_series.to_numpy()
        lambda_frames.append(lambda_df)

    params = pd.DataFrame(param_rows).sort_values("표준버스정류장ID").reset_index(drop=True)
    lambdas = (
        pd.concat(lambda_frames, ignore_index=True)
        .sort_values(["표준버스정류장ID", "시간대"])
        .reset_index(drop=True)
    )
    return params, lambdas


def run(hourly_path: Path, out_dir: Path) -> None:
    """Read corridor_hourly.parquet, calibrate every stop, write both outputs."""
    hourly = pd.read_parquet(hourly_path)
    params, lambdas = calibrate_corridor(hourly)

    out_dir.mkdir(parents=True, exist_ok=True)
    params.to_parquet(out_dir / "calibration_params.parquet", index=False)
    lambdas.to_parquet(out_dir / "lambda_estimates.parquet", index=False)


if __name__ == "__main__":
    run(
        Path("data/processed/corridor_hourly.parquet"),
        Path("data/processed"),
    )
