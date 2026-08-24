"""Tests for the Seoul TOPIS real-time arrival fetcher (issue #48)."""

import httpx
import pytest

from stationcast.ingest import realtime_arrival
from stationcast.ingest.realtime_arrival import ArrivalInfoUnavailable, fetch_arrivals

_SUCCESS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ServiceResult><comMsgHeader/><msgHeader><headerCd>0</headerCd>
<headerMsg>정상적으로 처리되었습니다.</headerMsg><itemCount>1</itemCount></msgHeader>
<msgBody><itemList><busRouteAbrv>101</busRouteAbrv><busRouteId>100100006</busRouteId>
<adirection>서소문</adirection><arrmsg1>3분후[1번째 전]</arrmsg1>
<arrmsg2>11분후[5번째 전]</arrmsg2><congestion1>3</congestion1>
<congestion2>3</congestion2></itemList></msgBody></ServiceResult>"""

_NO_DATA_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ServiceResult><comMsgHeader/><msgHeader><headerCd>4</headerCd>
<headerMsg>결과가 없습니다.</headerMsg><itemCount>0</itemCount></msgHeader>
<msgBody/></ServiceResult>"""

_ERROR_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ServiceResult><comMsgHeader/><msgHeader><headerCd>7</headerCd>
<headerMsg>내부 오류</headerMsg><itemCount>0</itemCount></msgHeader>
<msgBody/></ServiceResult>"""


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEOUL_BUS_API_KEY", "test-key")


def test_fetch_arrivals_parses_items_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        realtime_arrival._client, "get", lambda *a, **kw: _FakeResponse(_SUCCESS_XML)
    )

    items = fetch_arrivals("01014")

    assert len(items) == 1
    assert items[0]["busRouteAbrv"] == "101"
    assert items[0]["arrmsg1"] == "3분후[1번째 전]"


def test_fetch_arrivals_returns_empty_list_when_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    # headerCd=4 ("결과가 없습니다") is a legitimate "nothing scheduled right
    # now" state, not a failure -- must not raise.
    monkeypatch.setattr(
        realtime_arrival._client, "get", lambda *a, **kw: _FakeResponse(_NO_DATA_XML)
    )

    assert fetch_arrivals("01014") == []


def test_fetch_arrivals_raises_on_unknown_header_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(realtime_arrival._client, "get", lambda *a, **kw: _FakeResponse(_ERROR_XML))

    with pytest.raises(ArrivalInfoUnavailable, match="headerCd=7"):
        fetch_arrivals("01014")


def test_fetch_arrivals_raises_on_http_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        realtime_arrival._client,
        "get",
        lambda *a, **kw: _FakeResponse('{"error":"Unauthorized"}', status_code=401),
    )

    with pytest.raises(ArrivalInfoUnavailable):
        fetch_arrivals("01014")


def test_fetch_arrivals_raises_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_timeout(*a: object, **kw: object) -> None:
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(realtime_arrival._client, "get", _raise_timeout)

    with pytest.raises(ArrivalInfoUnavailable):
        fetch_arrivals("01014")


def test_fetch_arrivals_raises_on_malformed_xml(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        realtime_arrival._client, "get", lambda *a, **kw: _FakeResponse("not xml at all <<<")
    )

    with pytest.raises(ArrivalInfoUnavailable, match="not valid XML"):
        fetch_arrivals("01014")


def test_fetch_arrivals_raises_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SEOUL_BUS_API_KEY", raising=False)

    with pytest.raises(ArrivalInfoUnavailable, match="SEOUL_BUS_API_KEY"):
        fetch_arrivals("01014")


def test_fetch_arrivals_sends_url_decoded_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # .env may store the key percent-encoded (e.g. containing %2F/%3D) --
    # httpx's own params= encoding handles that, so the key must be
    # decoded first or authentication double-encodes and fails.
    monkeypatch.setenv("SEOUL_BUS_API_KEY", "abc%2Fdef%3D%3D")
    captured = {}

    def _fake_get(url: str, params: dict[str, str], timeout: float) -> _FakeResponse:
        captured["serviceKey"] = params["serviceKey"]
        return _FakeResponse(_NO_DATA_XML)

    monkeypatch.setattr(realtime_arrival._client, "get", _fake_get)

    fetch_arrivals("01014")

    assert captured["serviceKey"] == "abc/def=="
