"""Tests for congestion grading (issue #12)."""

import pandas as pd
import pytest

from stationcast.estimator.congestion import compute_thresholds, grade_wait

THRESHOLDS = (50.0, 100.0)


def test_grade_wait_below_p70_is_여유() -> None:
    assert grade_wait(w=30.0, thresholds=THRESHOLDS) == "여유"


def test_grade_wait_at_p70_is_여유() -> None:
    assert grade_wait(w=50.0, thresholds=THRESHOLDS) == "여유"


def test_grade_wait_just_above_p70_is_보통() -> None:
    assert grade_wait(w=50.01, thresholds=THRESHOLDS) == "보통"


def test_grade_wait_at_p90_is_보통() -> None:
    assert grade_wait(w=100.0, thresholds=THRESHOLDS) == "보통"


def test_grade_wait_just_above_p90_is_혼잡() -> None:
    assert grade_wait(w=100.01, thresholds=THRESHOLDS) == "혼잡"


def test_grade_wait_well_above_p90_is_혼잡() -> None:
    assert grade_wait(w=500.0, thresholds=THRESHOLDS) == "혼잡"


def test_grade_wait_negative_w_is_여유() -> None:
    # wait_population doesn't clamp negative W; a value below p70 is 여유
    # whether or not it's physically meaningful.
    assert grade_wait(w=-5.0, thresholds=THRESHOLDS) == "여유"


def test_compute_thresholds_returns_p70_and_p90_of_every_row() -> None:
    wait = pd.DataFrame({"W": [float(w) for w in range(1, 101)]})

    result = compute_thresholds(wait)

    assert list(result.columns) == ["p70", "p90"]
    assert len(result) == 1
    assert result["p70"].iloc[0] == pytest.approx(70.3)
    assert result["p90"].iloc[0] == pytest.approx(90.1)


def test_compute_thresholds_ranks_across_hours_not_within_each_hour() -> None:
    # Two hours with very different levels: a quiet hour (1~4 people) and a
    # busy one (100~400). Per-hour percentiles would grade the quiet hour's
    # top rows 혼잡; a single global cutoff must not.
    wait = pd.DataFrame(
        {
            "시간대": [4, 4, 4, 4, 8, 8, 8, 8],
            "W": [1.0, 2.0, 3.0, 4.0, 100.0, 200.0, 300.0, 400.0],
        }
    )

    thresholds = compute_thresholds(wait)
    p70, p90 = float(thresholds["p70"].iloc[0]), float(thresholds["p90"].iloc[0])

    assert all(grade_wait(w, (p70, p90)) == "여유" for w in [1.0, 2.0, 3.0, 4.0])
    assert grade_wait(400.0, (p70, p90)) == "혼잡"
