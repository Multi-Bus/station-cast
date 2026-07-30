"""Queue balance equation — basic implementation (S1, issue #4).

Computes the per-stop waiting population time series W(s,t) from the
corridor's hourly boarding/alighting totals, per the queue balance
equation in ARCHITECTURE.md:

    W(s,t) = W(s,t-1) + A_new(s,t) + A_transfer(s,t) - B(s,t)

This is intentionally the *basic* S1 version, scoped narrowly to the
recursion itself:

- A_transfer(s,t) = alighting(s,t) * transfer_rate, where transfer_rate
  is a placeholder constant, not yet calibrated per stop. Calibration
  against real boarding data (via optimization) is S2 work.
- A_new(s,t) (new arrivals, lambda) defaults to 0. No arrival-rate
  estimate exists yet, and inventing one without calibration would just
  be a made-up number; S2's features/ work replaces this default.
- Negative W values are NOT clamped here. Physical-constraint checking
  (non-negativity, day-end closure) is a separate concern (issue #5,
  validate/) so it has real violations to measure and report.
"""

from pathlib import Path

import pandas as pd

DEFAULT_TRANSFER_RATE = 0.3
"""S1 placeholder: fraction of alighting passengers assumed to transfer
and wait to board at the same stop. Not yet calibrated per stop -- S2
fits this via optimization against real boarding data (ARCHITECTURE.md)."""


def compute_wait_series(
    boarding: pd.Series,
    alighting: pd.Series,
    transfer_rate: float = DEFAULT_TRANSFER_RATE,
    arrival_rate: pd.Series | float = 0.0,
    w0: float = 0.0,
) -> pd.Series:
    """Compute W(t) for a single stop via the queue balance recursion.

    ``boarding`` and ``alighting`` must be the same length and share the
    same index, ordered by hour ascending. ``arrival_rate`` may be a
    constant applied to every hour or a Series aligned to the same index.

    Returned values are not clamped to be non-negative; see validate/
    (issue #5) for constraint checking.
    """
    if len(boarding) != len(alighting):
        raise ValueError("boarding and alighting must be the same length")
    if not boarding.index.equals(alighting.index):
        raise ValueError("boarding and alighting must share the same index")

    if isinstance(arrival_rate, pd.Series):
        if not arrival_rate.index.equals(boarding.index):
            raise ValueError("arrival_rate index must match boarding/alighting")
        lam = arrival_rate.to_numpy(dtype="float64")
    else:
        lam = [float(arrival_rate)] * len(boarding)

    transfer_in = alighting.to_numpy(dtype="float64") * transfer_rate
    board = boarding.to_numpy(dtype="float64")

    values: list[float] = []
    prev = float(w0)
    for i in range(len(board)):
        prev = prev + lam[i] + transfer_in[i] - board[i]
        values.append(prev)

    return pd.Series(values, index=boarding.index, name="W")


def compute_corridor_wait(
    hourly: pd.DataFrame,
    transfer_rate: float = DEFAULT_TRANSFER_RATE,
) -> pd.DataFrame:
    """Apply compute_wait_series to every stop in a corridor_hourly-shaped frame.

    ``hourly`` must have columns 표준버스정류장ID, 정류장명, 시간대, 승차, 하차
    (see data/README.md). Each stop is computed independently (the queue
    balance model is stop-scoped, not route-scoped). Returns one row per
    (stop, hour) with a ``W`` column, sorted by stop then hour.
    """
    frames = []
    for _stop_id, group in hourly.groupby("표준버스정류장ID", sort=False):
        ordered = group.sort_values("시간대")
        wait = compute_wait_series(
            boarding=ordered["승차"],
            alighting=ordered["하차"],
            transfer_rate=transfer_rate,
        )
        result = ordered[["표준버스정류장ID", "정류장명", "시간대"]].copy()
        result["W"] = wait.to_numpy()
        frames.append(result)

    return (
        pd.concat(frames, ignore_index=True)
        .sort_values(["표준버스정류장ID", "시간대"])
        .reset_index(drop=True)
    )


def run(
    hourly_path: Path,
    out_path: Path,
    transfer_rate: float = DEFAULT_TRANSFER_RATE,
) -> None:
    """Read corridor_hourly.parquet, compute W(s,t) for every stop, write result."""
    hourly = pd.read_parquet(hourly_path)
    result = compute_corridor_wait(hourly, transfer_rate=transfer_rate)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(out_path, index=False)


if __name__ == "__main__":
    run(
        Path("data/processed/corridor_hourly.parquet"),
        Path("data/processed/corridor_wait.parquet"),
    )
