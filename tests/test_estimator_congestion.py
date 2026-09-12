"""Tests for congestion grading (issue #12)."""

import pytest

from stationcast.estimator.congestion import grade_wait


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
