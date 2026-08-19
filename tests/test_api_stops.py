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
            "W": [12.5, 30.0, 4.0],
        }
    )
    capacity = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP_A, STOP_B],
            "포용인원": [20.0, 10.0],
        }
    )
    weather = pd.DataFrame(
        {
            # 20260101 목요일이지만 신정(공휴일), 20260102 금(평일)
            "사용일자": [20260101, 20260102],
            "평균기온": [-2.5, -1.0],
            "강수량": [0.0, 3.2],
            "습도": [55.0, 70.0],
            "신적설": [0.0, 1.5],
            "평균풍속": [2.1, 3.4],
        }
    )
    holiday = pd.DataFrame({"사용일자": [20260101], "공휴일명": ["신정"]})
    weekday_holiday_factor = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP_A, STOP_B],
            "보정계수_승차": [0.85, 1.2],
        }
    )
    return CorridorData(
        stops=stops,
        wait=wait,
        capacity=capacity,
        weather=weather,
        holiday=holiday,
        weekday_holiday_factor=weekday_holiday_factor,
    )


@pytest.fixture
def client(corridor_data: CorridorData) -> TestClient:
    app.dependency_overrides[get_corridor_data] = lambda: corridor_data
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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


def test_congestion_returns_raw_estimate_without_clamping(client: TestClient) -> None:
    # wait_population's W is always >= 0 by construction (sum of
    # non-negative boarding times non-negative wait), so the API no longer
    # needs to clamp it -- it's a plain pass-through.
    response = client.get(f"/stops/{STOP_B}/congestion", params={"hour": 8})

    assert response.status_code == 200
    body = response.json()
    assert body["estimated_wait"] == 4.0
    assert body["grade"] == "여유"


def test_congestion_defaults_to_current_hour_when_omitted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("stationcast.api.main._current_hour", lambda: 9)
    response = client.get(f"/stops/{STOP_A}/congestion")

    assert response.status_code == 200
    body = response.json()
    assert body["hour"] == 9
    assert body["estimated_wait"] == 30.0


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


def test_timeline_returns_raw_estimate_without_clamping(client: TestClient) -> None:
    response = client.get(f"/stops/{STOP_B}/timeline")

    assert response.status_code == 200
    body = response.json()
    assert body["timeline"] == [{"hour": 8, "estimated_wait": 4.0, "grade": "여유"}]


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
        {"stop_id": STOP_B, "name": "종로1가", "estimated_wait": 4.0},
    ]


def test_corridor_defaults_to_current_hour_when_omitted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("stationcast.api.main._current_hour", lambda: 8)
    response = client.get("/corridor")

    assert response.status_code == 200
    body = response.json()
    assert body["hour"] == 8
    assert body["stops"] == [
        {"stop_id": STOP_A, "name": "명동성당", "estimated_wait": 12.5},
        {"stop_id": STOP_B, "name": "종로1가", "estimated_wait": 4.0},
    ]


def test_corridor_empty_at_hour_with_no_data(client: TestClient) -> None:
    response = client.get("/corridor", params={"hour": 15})

    assert response.status_code == 200
    assert response.json() == {"hour": 15, "stops": []}


def test_context_returns_weather_and_holiday_note(client: TestClient) -> None:
    # 20260101 is a Thursday but flagged as 신정 in the holiday fixture, so
    # holiday takes priority over weekday in day_type, and STOP_A's
    # 보정계수_승차=0.85 becomes "15% lower than usual".
    response = client.get(f"/stops/{STOP_A}/context", params={"date": 20260101})

    assert response.status_code == 200
    assert response.json() == {
        "stop_id": STOP_A,
        "name": "명동성당",
        "date": 20260101,
        "day_type": "공휴일",
        "temperature": -2.5,
        "precipitation": 0.0,
        "humidity": 55.0,
        "snowfall": 0.0,
        "wind_speed": 2.1,
        "congestion_note": "공휴일이라 평소보다 혼잡도가 약 15% 낮을 것으로 예상됩니다.",
    }


def test_context_weekday_returns_baseline_note(client: TestClient) -> None:
    # 20260102 is a plain Friday (not weekend, not holiday) -- day_type is
    # 평일, so the note is a flat baseline regardless of STOP_B's factor.
    response = client.get(f"/stops/{STOP_B}/context", params={"date": 20260102})

    assert response.status_code == 200
    body = response.json()
    assert body["day_type"] == "평일"
    assert body["congestion_note"] == "평일이라 평소와 비슷한 혼잡도가 예상됩니다."


def test_context_defaults_to_current_date_when_omitted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("stationcast.api.main._current_date", lambda: 20260102)
    response = client.get(f"/stops/{STOP_B}/context")

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == 20260102
    assert body["day_type"] == "평일"


def test_context_unknown_stop_returns_404(client: TestClient) -> None:
    response = client.get("/stops/999999999/context", params={"date": 20260101})

    assert response.status_code == 404


def test_context_unknown_date_returns_404(client: TestClient) -> None:
    response = client.get(f"/stops/{STOP_A}/context", params={"date": 20260201})

    assert response.status_code == 404


def test_arrivals_returns_routes_for_stop(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "stationcast.api.main.fetch_arrivals",
        lambda ars_id: [
            {
                "busRouteAbrv": "101",
                "busRouteId": "100100006",
                "adirection": "서소문",
                "arrmsg1": "3분후[1번째 전]",
                "arrmsg2": "11분후[5번째 전]",
                "congestion1": "3",
                "congestion2": "3",
            }
        ],
    )

    response = client.get(f"/stops/{STOP_A}/arrivals")

    assert response.status_code == 200
    assert response.json() == {
        "stop_id": STOP_A,
        "name": "명동성당",
        "available": True,
        "message": None,
        "arrivals": [
            {
                "route_name": "101",
                "route_id": "100100006",
                "direction": "서소문",
                "arrival_message_1": "3분후[1번째 전]",
                "arrival_message_2": "11분후[5번째 전]",
                "congestion_1": "3",
                "congestion_2": "3",
            }
        ],
    }


def test_arrivals_uses_stop_ars_number_not_stop_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = {}

    def _fake_fetch(ars_id: str) -> list[dict]:
        captured["ars_id"] = ars_id
        return []

    monkeypatch.setattr("stationcast.api.main.fetch_arrivals", _fake_fetch)

    client.get(f"/stops/{STOP_A}/arrivals")

    assert captured["ars_id"] == "01010"  # STOP_A's ARS번호, not its 표준버스정류장ID


def test_arrivals_available_false_when_topis_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from stationcast.ingest.realtime_arrival import ArrivalInfoUnavailable

    def _raise(ars_id: str) -> list[dict]:
        raise ArrivalInfoUnavailable("timed out")

    monkeypatch.setattr("stationcast.api.main.fetch_arrivals", _raise)

    response = client.get(f"/stops/{STOP_A}/arrivals")

    # A TOPIS outage must not surface as a 500 -- issue #48's graceful
    # degradation requirement.
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["arrivals"] == []
    assert body["message"] == "일시적으로 도착정보를 가져올 수 없습니다."


def test_arrivals_unknown_stop_returns_404(client: TestClient) -> None:
    response = client.get("/stops/999999999/arrivals")

    assert response.status_code == 404
