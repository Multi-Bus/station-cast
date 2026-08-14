"""Tests for congestion grading (issue #12)."""

import pandas as pd
import pytest

from stationcast.estimator.congestion import add_congestion_grade, grade_wait


def test_grade_wait_below_spare_ratio_is_여유() -> None:
    assert grade_wait(w=30.0, capacity=100.0) == "여유"


def test_grade_wait_at_spare_boundary_is_여유() -> None:
    assert grade_wait(w=50.0, capacity=100.0) == "여유"


def test_grade_wait_just_above_spare_boundary_is_보통() -> None:
    assert grade_wait(w=50.01, capacity=100.0) == "보통"


def test_grade_wait_at_normal_boundary_is_보통() -> None:
    assert grade_wait(w=100.0, capacity=100.0) == "보통"


def test_grade_wait_just_above_normal_boundary_is_혼잡() -> None:
    assert grade_wait(w=100.01, capacity=100.0) == "혼잡"


def test_grade_wait_well_above_normal_boundary_is_혼잡() -> None:
    assert grade_wait(w=500.0, capacity=100.0) == "혼잡"


def test_grade_wait_negative_w_is_여유() -> None:
    # compute_wait_series doesn't clamp negative W; a negative ratio is
    # trivially <= 0.5, so it grades as 여유 rather than erroring.
    assert grade_wait(w=-5.0, capacity=100.0) == "여유"


@pytest.mark.parametrize("capacity", [0.0, -10.0])
def test_grade_wait_rejects_nonpositive_capacity(capacity: float) -> None:
    with pytest.raises(ValueError, match="capacity must be positive"):
        grade_wait(w=10.0, capacity=capacity)


def _wait_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "표준버스정류장ID": [1, 1, 2, 2],
            "정류장명": ["A", "A", "B", "B"],
            "시간대": [0, 1, 0, 1],
            "W": [40.0, 80.0, 300.0, 10.0],
        }
    )


def test_add_congestion_grade_hand_computed() -> None:
    wait_df = _wait_df()
    capacity_df = pd.DataFrame({"표준버스정류장ID": [1, 2], "포용인원": [100.0, 100.0]})

    result = add_congestion_grade(wait_df, capacity_df)
    grades = result.set_index(["표준버스정류장ID", "시간대"])["혼잡도등급"]

    # stop 1: W=40 -> 40/100=0.4 -> 여유; W=80 -> 0.8 -> 보통
    # stop 2: W=300 -> 3.0 -> 혼잡; W=10 -> 0.1 -> 여유
    assert grades[(1, 0)] == "여유"
    assert grades[(1, 1)] == "보통"
    assert grades[(2, 0)] == "혼잡"
    assert grades[(2, 1)] == "여유"

    # the intermediate capacity column shouldn't leak into the output
    assert "포용인원" not in result.columns


def test_add_congestion_grade_raises_on_missing_capacity() -> None:
    wait_df = _wait_df()
    capacity_df = pd.DataFrame({"표준버스정류장ID": [1], "포용인원": [100.0]})

    with pytest.raises(ValueError, match=r"missing stops: \[2\]"):
        add_congestion_grade(wait_df, capacity_df)
