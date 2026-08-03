"""Tests for physical constraint checks — non-negativity and day-end closure (issue #5)."""

import pandas as pd
import pytest

from stationcast.validate.physical_constraints import (
    build_validation_report,
    day_end_closure_residual,
    non_negativity_report,
    non_negativity_violation_rate,
)


def _wait_df() -> pd.DataFrame:
    # Stop 1, hours 0,1,2: W = -5, 3, 0   -> 1/3 violations, day-end (hour 2) W=0
    # Stop 2, hours 0,1,2: W = -2, -1, -4 -> 3/3 violations, day-end (hour 2) W=-4
    return pd.DataFrame(
        {
            "표준버스정류장ID": [1, 1, 1, 2, 2, 2],
            "정류장명": ["A", "A", "A", "B", "B", "B"],
            "시간대": [0, 1, 2, 0, 1, 2],
            "W": [-5.0, 3.0, 0.0, -2.0, -1.0, -4.0],
        }
    )


def test_non_negativity_violation_rate_across_whole_corridor() -> None:
    assert non_negativity_violation_rate(_wait_df()) == pytest.approx(4 / 6)


def test_non_negativity_violation_rate_rejects_empty() -> None:
    empty = pd.DataFrame(columns=["표준버스정류장ID", "정류장명", "시간대", "W"])
    with pytest.raises(ValueError, match="empty"):
        non_negativity_violation_rate(empty)


def test_non_negativity_report_per_stop() -> None:
    report = non_negativity_report(_wait_df())

    stop1 = report[report["표준버스정류장ID"] == 1].iloc[0]
    assert stop1["총_시간대수"] == 3
    assert stop1["위반_횟수"] == 1
    assert stop1["위반율"] == pytest.approx(1 / 3)

    stop2 = report[report["표준버스정류장ID"] == 2].iloc[0]
    assert stop2["총_시간대수"] == 3
    assert stop2["위반_횟수"] == 3
    assert stop2["위반율"] == pytest.approx(1.0)


def test_day_end_closure_residual_uses_specified_hour() -> None:
    result = day_end_closure_residual(_wait_df(), last_hour=2)

    stop1 = result[result["표준버스정류장ID"] == 1].iloc[0]
    assert stop1["일마감_W"] == 0.0
    assert stop1["잔차"] == 0.0

    stop2 = result[result["표준버스정류장ID"] == 2].iloc[0]
    assert stop2["일마감_W"] == -4.0
    assert stop2["잔차"] == 4.0


def test_day_end_closure_residual_rejects_missing_hour() -> None:
    with pytest.raises(ValueError, match="시간대=99"):
        day_end_closure_residual(_wait_df(), last_hour=99)


def test_build_validation_report_aggregates_both_metrics() -> None:
    summary = build_validation_report(_wait_df(), last_hour=2)

    assert summary["비음수_위반율"] == pytest.approx(4 / 6)
    # residuals: stop1=0.0, stop2=4.0 -> mean = 2.0
    assert summary["일마감_평균잔차"] == pytest.approx(2.0)
