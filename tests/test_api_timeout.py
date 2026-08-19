"""Response-time and timeout hardening for the S2 endpoints (S3, issue #18)."""

import time

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from stationcast.api.data import CorridorData, get_corridor_data
from stationcast.api.main import REQUEST_TIMEOUT_SECONDS, app

STOP_A = 100000385


@pytest.fixture
def corridor_data() -> CorridorData:
    stops = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP_A],
            "정류장명": ["명동성당"],
            "ARS번호": ["01010"],
            "X좌표": [126.987],
            "Y좌표": [37.563],
            "정류소 타입": ["중앙차로"],
        }
    )
    wait = pd.DataFrame(
        {
            "표준버스정류장ID": [STOP_A],
            "정류장명": ["명동성당"],
            "시간대": [8],
            "W": [12.5],
        }
    )
    capacity = pd.DataFrame({"표준버스정류장ID": [STOP_A], "포용인원": [20.0]})
    weather = pd.DataFrame(
        {
            "사용일자": [20260101],
            "평균기온": [-2.5],
            "강수량": [0.0],
            "습도": [55.0],
            "신적설": [0.0],
            "평균풍속": [2.1],
        }
    )
    holiday = pd.DataFrame({"사용일자": [20260101], "공휴일명": ["신정"]})
    weekday_holiday_factor = pd.DataFrame(
        {"표준버스정류장ID": [STOP_A], "보정계수_승차": [0.85]}
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


@pytest.mark.parametrize(
    "path",
    [
        "/stops",
        f"/stops/{STOP_A}/congestion?hour=8",
        f"/stops/{STOP_A}/timeline",
        "/corridor?hour=8",
        f"/stops/{STOP_A}/context?date=20260101",
    ],
)
def test_endpoint_responds_within_timeout(client: TestClient, path: str) -> None:
    start = time.monotonic()
    response = client.get(path)
    elapsed = time.monotonic() - start

    assert response.status_code == 200
    assert elapsed < REQUEST_TIMEOUT_SECONDS


def test_slow_handler_is_cut_off_with_504(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The sync handler runs in a threadpool, so cancelling the awaiting
    # coroutine at REQUEST_TIMEOUT_SECONDS doesn't stop the underlying
    # thread's time.sleep -- only the response the client sees is cut off,
    # which is what actually matters here.
    def slow_current_hour() -> int:
        time.sleep(REQUEST_TIMEOUT_SECONDS + 1.0)
        return 8

    monkeypatch.setattr("stationcast.api.main._current_hour", slow_current_hour)

    response = client.get(f"/stops/{STOP_A}/congestion")

    assert response.status_code == 504
    assert response.json() == {"detail": "request timed out"}
