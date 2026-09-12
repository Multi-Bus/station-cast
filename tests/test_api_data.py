"""Tests for api/data.py's missing-data handling (issue #141).

A container started without the data volume mounted (or a local checkout
before scripts/build_processed.py has run) has no data/processed/ at all --
this should surface as a 503 the operator can act on, not a bare 500 from
whichever pd.read_parquet() happened to run first.
"""

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from stationcast.api.data import CorridorData, CorridorDataUnavailable, load_corridor_data
from stationcast.api.main import app


def test_load_corridor_data_raises_when_directory_is_empty(tmp_path: Path) -> None:
    with pytest.raises(CorridorDataUnavailable, match="corridor_stops.parquet"):
        load_corridor_data(data_dir=tmp_path)


def test_load_corridor_data_lists_every_missing_file(tmp_path: Path) -> None:
    # One file present, the rest missing -- the present one must not appear
    # in the error, and every missing one must.
    pd.DataFrame({"표준버스정류장ID": [1]}).to_parquet(tmp_path / "corridor_stops.parquet")

    with pytest.raises(CorridorDataUnavailable) as exc_info:
        load_corridor_data(data_dir=tmp_path)

    message = str(exc_info.value)
    assert "corridor_stops.parquet" not in message
    for name in (
        "corridor_wait.parquet",
        "weather_daily.parquet",
        "holiday_daily_all.parquet",
        "corridor_features_daily.parquet",
        "weekday_weather_factor.parquet",
    ):
        assert name in message


def test_api_returns_503_not_500_when_data_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # Data is loaded once at startup by main.py's lifespan, not lazily on
    # the first request, so this has to make load_corridor_data() fail
    # *before* the app starts up -- swap it on the main module (where
    # lifespan's `from stationcast.api.data import load_corridor_data`
    # bound it), then enter the TestClient as a context manager, which is
    # what actually runs the ASGI lifespan startup/shutdown events (a plain
    # TestClient(app) does not). This exercises the real path end to end:
    # lifespan -> captured exception -> get_corridor_data -> the app's own
    # exception_handler(CorridorDataUnavailable), the same as a container
    # started without the data volume mounted.
    import stationcast.api.main as main_module

    def raise_unavailable() -> CorridorData:
        raise CorridorDataUnavailable("missing parquet files in data/processed: [...]")

    monkeypatch.setattr(main_module, "load_corridor_data", raise_unavailable)

    with TestClient(app) as client:
        response = client.get("/api/stops")
        assert response.status_code == 503
        assert "missing parquet files" in response.json()["detail"]
