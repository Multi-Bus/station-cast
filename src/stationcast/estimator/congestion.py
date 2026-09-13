"""Congestion grading for estimated wait counts W(s,t) (S2, issue #12).

Converts W into a three-tier label (여유/보통/혼잡) by comparing it to
Seoul-wide 70th/90th percentile thresholds of every (stop, hour) row's W,
rather than each stop's physical capacity: 포용인원 (platform-count-derived
capacity) was only ever field-surveyed for the 21-stop demo corridor, so it
doesn't exist at Seoul scale (~11,000 stops).

Thresholds are computed **globally** across every (stop, hour) row, not
per hour: a per-hour percentile would force roughly 10% of stops into
"혼잡" even at 4am, which is meaningless -- the global ranking keeps
legitimately quiet early-morning hours at "여유" while still grading every
stop on the same Seoul-wide scale (grade_basis="seoul_percentile" in the
API response):

- W <= p70 -> 여유 (하위 70%)
- W <= p90 -> 보통 (70~90%)
- W >  p90 -> 혼잡 (상위 10%)
"""

from pathlib import Path

import numpy as np
import pandas as pd

GRADES = ("여유", "보통", "혼잡")


def grade_wait(w: float, thresholds: tuple[float, float]) -> str:
    """Grade a single W value against Seoul-wide (p70, p90) thresholds.

    thresholds comes from compute_thresholds() below -- a global cutoff,
    not a per-stop or per-hour value.
    """
    p70, p90 = thresholds
    if w <= p70:
        return "여유"
    if w <= p90:
        return "보통"
    return "혼잡"


def compute_thresholds(wait: pd.DataFrame) -> pd.DataFrame:
    """70th/90th percentile of every (stop, hour) row's W, Seoul-wide.

    Computed once across the whole table (not grouped by 시간대) -- see
    module docstring for why per-hour percentiles would be meaningless.
    """
    p70, p90 = np.quantile(wait["W"], [0.70, 0.90])
    return pd.DataFrame({"p70": [float(p70)], "p90": [float(p90)]})


def run(wait_path: Path, out_path: Path) -> None:
    """Read corridor_wait.parquet, compute Seoul-wide grade thresholds, write them."""
    wait = pd.read_parquet(wait_path)
    thresholds = compute_thresholds(wait)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    thresholds.to_parquet(out_path, index=False)


if __name__ == "__main__":
    run(
        Path("data/processed/corridor_wait.parquet"),
        Path("data/processed/grade_thresholds.parquet"),
    )
