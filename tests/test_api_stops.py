"""Tests for /stops, /congestion, /timeline, /corridor (S2, issue #13).

Uses a small in-memory CorridorData fixture via dependency_overrides instead
of real parquet files, since data/processed/ is not committed (see
api/data.py's docstring).
"""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from stationcast.api.data import CorridorData, get_corridor_data
from stationcast.api.main import app

STOP_A = 100000385
STOP_B = 100000386


@pytest.fixture
def corridor_data() -> CorridorData:
    stops = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP_A, STOP_B],
            "정류장명": ["명동성당", "종로1가"],
            "ARS번호": ["01010", "01011"],
            "X좌표": [126.987, 126.981],
            "Y좌표": [37.563, 37.570],
            "정류소 타입": ["중앙차로", "중앙차로"],
        }
    )
    wait = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP_A, STOP_A, STOP_B],
            "정류장명": ["명동성당", "명동성당", "종로1가"],
            "시간대": [8, 9, 8],
            "W": [12.5, 30.0, -3.0],
        }
    )
    capacity = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP_A, STOP_B],
            "포용인원": [20.0, 10.0],
        }
    )
    return CorridorData(stops=stops, wait=wait, capacity=capacity)


@pytest.fixture
def client(corridor_data: CorridorData) -> TestClient:
    app.dependency_overrides[get_corridor_data] = lambda: corridor_data
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_list_stops(client: TestClient) -> None:
    response = client.get("/stops")

    assert response.status_code == 200
    body = response.json()
    assert len(body["stops"]) == 2
    assert body["stops"][0] == {
        "stop_id": STOP_A,
        "name": "명동성당",
        "ars_number": "01010",
        "lat": 37.563,
        "lon": 126.987,
        "stop_type": "중앙차로",
    }


def test_congestion_returns_estimate_and_grade_for_given_hour(client: TestClient) -> None:
    response = client.get(f"/stops/{STOP_A}/congestion", params={"hour": 9})

    assert response.status_code == 200
    assert response.json() == {
        "stop_id": STOP_A,
        "name": "명동성당",
        "hour": 9,
        "estimated_wait": 30.0,
        "grade": "혼잡",
    }


def test_congestion_unknown_stop_returns_404(client: TestClient) -> None:
    response = client.get("/stops/999999999/congestion", params={"hour": 9})

    assert response.status_code == 404


def test_congestion_unknown_hour_returns_404(client: TestClient) -> None:
    response = client.get(f"/stops/{STOP_A}/congestion", params={"hour": 3})

    assert response.status_code == 404


def test_congestion_rejects_hour_out_of_range(client: TestClient) -> None:
    response = client.get(f"/stops/{STOP_A}/congestion", params={"hour": 24})

    assert response.status_code == 422


def test_timeline_returns_full_curve_sorted_by_hour_with_grade(client: TestClient) -> None:
    response = client.get(f"/stops/{STOP_A}/timeline")

    assert response.status_code == 200
    body = response.json()
    assert body["stop_id"] == STOP_A
    assert body["timeline"] == [
        {"hour": 8, "estimated_wait": 12.5, "grade": "보통"},
        {"hour": 9, "estimated_wait": 30.0, "grade": "혼잡"},
    ]


def test_timeline_unknown_stop_returns_404(client: TestClient) -> None:
    response = client.get("/stops/999999999/timeline")

    assert response.status_code == 404


def test_corridor_returns_every_stop_at_given_hour(client: TestClient) -> None:
    response = client.get("/corridor", params={"hour": 8})

    assert response.status_code == 200
    body = response.json()
    assert body["hour"] == 8
    assert body["stops"] == [
        {"stop_id": STOP_A, "name": "명동성당", "estimated_wait": 12.5},
        {"stop_id": STOP_B, "name": "종로1가", "estimated_wait": -3.0},
    ]


def test_corridor_empty_at_hour_with_no_data(client: TestClient) -> None:
    response = client.get("/corridor", params={"hour": 15})

    assert response.status_code == 200
    assert response.json() == {"hour": 15, "stops": []}
