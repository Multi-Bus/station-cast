"""Tests for the KMA short-range forecast fetcher (실시간 날씨 연동)."""

from datetime import datetime

import httpx
import pytest

from stationcast.ingest import weather_forecast
from stationcast.ingest.weather_forecast import (
    DailyForecast,
    ForecastUnavailable,
    build_daily_forecast,
    fetch_forecast_items,
    is_precipitating,
    latlon_to_grid,
    precipitation_label,
)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    weather_forecast._cache.clear()


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KMA_FORECAST_API_KEY", "test-key")


class _FakeResponse:
    def __init__(self, json_body: dict | None = None, status_code: int = 200):
        self._json_body = json_body
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]

    def json(self) -> dict | None:
        return self._json_body


def _success_body(items: list[dict[str, str]]) -> dict:
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL_SERVICE"},
            "body": {"items": {"item": items}},
        }
    }


def test_latlon_to_grid_matches_known_seoul_reference_point() -> None:
    # 서울(종로구)/서울시청 for KMA's grid is commonly cited as (60, 127).
    assert latlon_to_grid(37.5665, 126.9780) == (60, 127)
    assert latlon_to_grid(37.570238, 126.986535) == (60, 127)  # 종로2가(100000389)


def test_precipitation_label_maps_known_pty_codes() -> None:
    assert precipitation_label("0") == "맑음"
    assert precipitation_label("1") == "비"
    assert precipitation_label("3") == "눈"


def test_precipitation_label_passes_through_unknown_codes() -> None:
    assert precipitation_label("99") == "99"


def test_is_precipitating_true_for_any_nonzero_pty() -> None:
    assert is_precipitating("0") is False
    assert is_precipitating("1") is True
    assert is_precipitating("3") is True


def test_fetch_forecast_items_returns_items_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    items = [{"category": "TMP", "fcstDate": "20260821", "fcstTime": "1200", "fcstValue": "28"}]
    monkeypatch.setattr("httpx.get", lambda *a, **kw: _FakeResponse(_success_body(items)))

    result = fetch_forecast_items(now=datetime(2026, 8, 21, 12, 0))

    assert result == items


def test_fetch_forecast_items_caches_within_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def _fake_get(*a: object, **kw: object) -> _FakeResponse:
        calls["count"] += 1
        return _FakeResponse(_success_body([]))

    monkeypatch.setattr("httpx.get", _fake_get)

    now = datetime(2026, 8, 21, 12, 0)
    fetch_forecast_items(now=now)
    fetch_forecast_items(now=now)

    assert calls["count"] == 1


def test_fetch_forecast_items_raises_on_result_code_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"response": {"header": {"resultCode": "03", "resultMsg": "NODATA"}, "body": {}}}
    monkeypatch.setattr("httpx.get", lambda *a, **kw: _FakeResponse(body))

    with pytest.raises(ForecastUnavailable, match="resultCode=03"):
        fetch_forecast_items(now=datetime(2026, 8, 21, 12, 0))


def test_fetch_forecast_items_raises_on_http_error_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "httpx.get", lambda *a, **kw: _FakeResponse({"error": "Unauthorized"}, status_code=401)
    )

    with pytest.raises(ForecastUnavailable):
        fetch_forecast_items(now=datetime(2026, 8, 21, 12, 0))


def test_fetch_forecast_items_raises_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_timeout(*a: object, **kw: object) -> None:
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr("httpx.get", _raise_timeout)

    with pytest.raises(ForecastUnavailable):
        fetch_forecast_items(now=datetime(2026, 8, 21, 12, 0))


def test_fetch_forecast_items_raises_on_malformed_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("httpx.get", lambda *a, **kw: _FakeResponse({"unexpected": "shape"}))

    with pytest.raises(ForecastUnavailable, match="not parseable"):
        fetch_forecast_items(now=datetime(2026, 8, 21, 12, 0))


def test_fetch_forecast_items_raises_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KMA_FORECAST_API_KEY", raising=False)

    with pytest.raises(ForecastUnavailable, match="KMA_FORECAST_API_KEY"):
        fetch_forecast_items(now=datetime(2026, 8, 21, 12, 0))


def _items_for(date: str) -> list[dict[str, str]]:
    return [
        {"category": "TMX", "fcstDate": date, "fcstTime": "0600", "fcstValue": "31.0"},
        {"category": "TMP", "fcstDate": date, "fcstTime": "1100", "fcstValue": "27.5"},
        {"category": "TMP", "fcstDate": date, "fcstTime": "1400", "fcstValue": "29.0"},
        {"category": "REH", "fcstDate": date, "fcstTime": "1100", "fcstValue": "55"},
        {"category": "WSD", "fcstDate": date, "fcstTime": "1100", "fcstValue": "2.3"},
        {"category": "PTY", "fcstDate": date, "fcstTime": "1100", "fcstValue": "1"},
    ]


def test_build_daily_forecast_picks_the_nearest_time_slot() -> None:
    items = _items_for("20260821")

    forecast = build_daily_forecast(items, 20260821, now=datetime(2026, 8, 21, 11, 5))

    assert forecast == DailyForecast(
        date=20260821,
        temperature=27.5,
        high_temp=31.0,
        humidity=55.0,
        wind_speed=2.3,
        precipitation_type="비",
        is_precipitating=True,
    )


def test_build_daily_forecast_falls_back_to_max_tmp_when_tmx_missing() -> None:
    items = [item for item in _items_for("20260821") if item["category"] != "TMX"]

    forecast = build_daily_forecast(items, 20260821, now=datetime(2026, 8, 21, 11, 5))

    assert forecast.high_temp == 29.0  # max of the two TMP values


def test_build_daily_forecast_raises_when_date_not_in_window() -> None:
    items = _items_for("20260821")

    with pytest.raises(ForecastUnavailable):
        build_daily_forecast(items, 20260901, now=datetime(2026, 8, 21, 11, 5))
