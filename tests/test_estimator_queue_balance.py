"""Tests for the basic queue balance recursion (issue #4)."""

import pandas as pd
import pytest

from stationcast.estimator.queue_balance import (
    DEFAULT_TRANSFER_RATE,
    compute_corridor_wait,
    compute_wait_series,
)


def test_compute_wait_series_hand_computed() -> None:
    boarding = pd.Series([10, 5, 8])
    alighting = pd.Series([20, 10, 4])

    result = compute_wait_series(
        boarding, alighting, transfer_rate=0.5, arrival_rate=2, w0=0
    )

    # W0 = 0 + 2 + 20*0.5 - 10 = 2
    # W1 = 2 + 2 + 10*0.5 - 5  = 4
    # W2 = 4 + 2 +  4*0.5 - 8  = 0
    assert result.tolist() == [2.0, 4.0, 0.0]


def test_compute_wait_series_defaults_allow_negative_without_clamping() -> None:
    boarding = pd.Series([10, 5, 8])
    alighting = pd.Series([20, 10, 4])

    result = compute_wait_series(boarding, alighting)  # default transfer_rate, arrival_rate=0

    assert DEFAULT_TRANSFER_RATE == 0.3
    # W0 = 0 + 0 + 20*0.3 - 10 = -4
    # W1 = -4 + 0 + 10*0.3 - 5 = -6
    # W2 = -6 + 0 +  4*0.3 - 8 = -12.8
    assert result.tolist() == pytest.approx([-4.0, -6.0, -12.8])


def test_compute_wait_series_arrival_rate_as_series() -> None:
    boarding = pd.Series([10, 5])
    alighting = pd.Series([0, 0])
    arrival_rate = pd.Series([3, 4])

    result = compute_wait_series(
        boarding, alighting, transfer_rate=0.0, arrival_rate=arrival_rate, w0=1
    )

    # W0 = 1 + 3 + 0 - 10 = -6
    # W1 = -6 + 4 + 0 - 5 = -7
    assert result.tolist() == [-6.0, -7.0]


def test_compute_wait_series_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError, match="same length"):
        compute_wait_series(pd.Series([1, 2]), pd.Series([1, 2, 3]))


def test_compute_wait_series_rejects_index_mismatch() -> None:
    boarding = pd.Series([1, 2], index=[0, 1])
    alighting = pd.Series([1, 2], index=[5, 6])
    with pytest.raises(ValueError, match="same index"):
        compute_wait_series(boarding, alighting)


def _hourly_df() -> pd.DataFrame:
    # Deliberately unsorted by 시간대 to exercise compute_corridor_wait's sort.
    return pd.DataFrame(
        {
            "표준버스정류장ID": [1, 1, 2, 2],
            "정류장명": ["A", "A", "B", "B"],
            "시간대": [1, 0, 0, 1],
            "승차": [5, 10, 3, 3],
            "하차": [10, 20, 0, 0],
        }
    )


def test_compute_corridor_wait_computes_each_stop_independently_and_sorts() -> None:
    result = compute_corridor_wait(_hourly_df())

    assert list(result.columns) == ["표준버스정류장ID", "정류장명", "시간대", "W"]
    assert result[["표준버스정류장ID", "시간대"]].to_records(index=False).tolist() == [
        (1, 0),
        (1, 1),
        (2, 0),
        (2, 1),
    ]

    # Stop 1 (default transfer_rate=0.3): W0 = 20*0.3-10 = -4; W1 = -4+10*0.3-5 = -6
    stop1 = result[result["표준버스정류장ID"] == 1]["W"].tolist()
    assert stop1 == pytest.approx([-4.0, -6.0])

    # Stop 2 (no alighting): W0 = -3; W1 = -3-3 = -6
    stop2 = result[result["표준버스정류장ID"] == 2]["W"].tolist()
    assert stop2 == pytest.approx([-3.0, -6.0])
