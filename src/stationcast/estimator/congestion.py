"""Congestion grading for estimated wait counts W(s,t) (S2, issue #12).

Converts W into a three-tier label (여유/보통/혼잡) by comparing it to each
stop's 포용인원(physical capacity) rather than a fixed headcount, since
stop size varies across the corridor and a fixed threshold would grade a
small stop as chronically 혼잡 and a large one as chronically 여유:

- W / capacity <= 0.5 -> 여유
- W / capacity <= 1.0 -> 보통
- W / capacity > 1.0  -> 혼잡

포용인원 isn't available from open data, so the team field-surveyed each
stop's 승차대(platform structure) count and set capacity at 10 people per
platform (see ingest/stop_capacity.py, where 포용인원 = 10 * 승차대개수).
The ratio thresholds above are that per-platform rule translated directly:
up to 5 people per platform is 여유, up to 10 is 보통, more is 혼잡.
"""

from pathlib import Path

import pandas as pd

GRADES = ("여유", "보통", "혼잡")

SPARE_RATIO = 0.5
NORMAL_RATIO = 1.0


def grade_wait(w: float, capacity: float) -> str:
    """Grade a single W value against a stop's capacity.

    capacity must be positive -- a zero or negative capacity makes the
    ratio undefined, not just an edge case to silently clamp.
    """
    if capacity <= 0:
        raise ValueError(f"capacity must be positive, got {capacity}")

    ratio = w / capacity
    if ratio <= SPARE_RATIO:
        return "여유"
    if ratio <= NORMAL_RATIO:
        return "보통"
    return "혼잡"


def add_congestion_grade(wait_df: pd.DataFrame, capacity_df: pd.DataFrame) -> pd.DataFrame:
    """Attach a 혼잡도등급 column to wait_df using per-stop capacity.

    wait_df: 표준버스정류장ID, ..., W (see estimator/scipy_calibration.py output)
    capacity_df: 표준버스정류장ID, 포용인원 (one row per stop)
    """
    merged = wait_df.merge(
        capacity_df[["표준버스정류장ID", "포용인원"]], on="표준버스정류장ID", how="left"
    )
    if merged["포용인원"].isna().any():
        missing_ids = merged.loc[merged["포용인원"].isna(), "표준버스정류장ID"].unique()
        missing = sorted(int(stop_id) for stop_id in missing_ids)
        raise ValueError(f"capacity_df is missing stops: {missing}")

    merged["혼잡도등급"] = merged.apply(lambda row: grade_wait(row["W"], row["포용인원"]), axis=1)
    return merged.drop(columns=["포용인원"])


def run(wait_path: Path, capacity_path: Path, out_path: Path) -> None:
    """Read a corridor_wait-shaped parquet + per-stop capacity, attach grades, write result.

    capacity_path must point to a parquet with 표준버스정류장ID, 포용인원
    (see ingest/stop_capacity.py's run() to generate it from the field
    survey's 승차대 counts).
    """
    wait_df = pd.read_parquet(wait_path)
    capacity_df = pd.read_parquet(capacity_path)
    graded = add_congestion_grade(wait_df, capacity_df)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    graded.to_parquet(out_path, index=False)

    print(graded["혼잡도등급"].value_counts())


if __name__ == "__main__":
    run(
        Path("data/processed/corridor_wait_scipy.parquet"),
        Path("data/processed/stop_capacity.parquet"),
        Path("data/processed/corridor_wait_graded.parquet"),
    )
