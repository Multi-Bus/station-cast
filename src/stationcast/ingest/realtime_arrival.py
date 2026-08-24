"""Seoul TOPIS real-time bus arrival info (issue #48).

Calls ``stationinfo/getStationByUid`` on ws.bus.go.kr with a stop's ARS
number (5-digit ARS번호, not the 9-digit 표준버스정류장ID used elsewhere in
this project) and returns every route currently serving that stop with its
next-arrival estimate.

This is a live display feature independent of estimator/wait_population.py:
W(s,t) is never derived from or combined with this data.
"""

import os
import xml.etree.ElementTree as ET
from urllib.parse import unquote

import httpx
from dotenv import load_dotenv

load_dotenv()

ARRIVAL_URL = "http://ws.bus.go.kr/api/rest/stationinfo/getStationByUid"
DEFAULT_TIMEOUT = 3.0

_client = httpx.Client(timeout=DEFAULT_TIMEOUT)

_NO_DATA_HEADER_CD = "4"
"""TOPIS's own code for "결과가 없습니다" -- no buses currently scheduled for
this stop, not a service failure. Returned as an empty arrival list rather
than raised as an error."""


class ArrivalInfoUnavailable(Exception):
    """Raised when TOPIS can't be reached or returns something other than
    success/no-data (network failure, timeout, HTTP error, malformed
    response, auth failure, or an undocumented headerCd). Callers should
    catch this and degrade gracefully rather than surface a 500 (issue #48)."""


def _service_key() -> str:
    """Read SEOUL_BUS_API_KEY from the environment, URL-decoded.
    """
    raw = os.environ.get("SEOUL_BUS_API_KEY")
    if not raw:
        raise ArrivalInfoUnavailable("SEOUL_BUS_API_KEY is not set")
    return unquote(raw)


def fetch_arrivals(ars_id: str, timeout: float = DEFAULT_TIMEOUT) -> list[dict[str, str | None]]:
    """Fetch every route's next-arrival info for one stop's ARS number.

    Returns one dict per route an empty list means TOPIS
    reached and answered but has nothing to report right now (headerCd 4),
    which is a legitimate state, not a failure.

    Raises ArrivalInfoUnavailable on anything that isn't success-or-no-data:
    network/timeout errors, non-2xx HTTP status, unparseable response, or
    any other headerCd (including auth failure, which TOPIS returns as a
    plain HTTP 401 rather than a headerCd -- caught by raise_for_status()).
    """
    try:
        response = _client.get(
            ARRIVAL_URL,
            params={"serviceKey": _service_key(), "arsId": ars_id},
            timeout=timeout,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ArrivalInfoUnavailable(f"TOPIS request failed: {exc}") from exc

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as exc:
        raise ArrivalInfoUnavailable(f"TOPIS response was not valid XML: {exc}") from exc

    header_cd = root.findtext("./msgHeader/headerCd")
    if header_cd == _NO_DATA_HEADER_CD:
        return []
    if header_cd != "0":
        header_msg = root.findtext("./msgHeader/headerMsg") or "unknown error"
        raise ArrivalInfoUnavailable(f"TOPIS returned headerCd={header_cd}: {header_msg}")

    return [
        {field.tag: field.text for field in item}
        for item in root.findall("./msgBody/itemList")
    ]
