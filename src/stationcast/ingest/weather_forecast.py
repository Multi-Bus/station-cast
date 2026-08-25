"""Real-time weather (KMA 단기예보 조회서비스, getVilageFcst) for /stops/{id}/context.

weather_daily.parquet only covers the historical corridor collection window,
so /stops/{id}/context 404s for any date outside it -- including "오늘" once
the window rolls past its end date. This module fills that gap by calling
KMA's short-range forecast API for the corridor's grid cell instead.
"""

import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import unquote

import httpx
from dotenv import load_dotenv

load_dotenv()

FORECAST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
DEFAULT_TIMEOUT = 3.0

_client = httpx.Client(timeout=DEFAULT_TIMEOUT)

_BASE_TIMES = ("0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300")
_BASE_TIME_PUBLISH_DELAY_MIN = 10

_CACHE_TTL_SECONDS = 3600
_cache: dict[tuple[str, str, int, int], tuple[float, list[dict[str, str]]]] = {}

# KMA's published LCC(Lambert Conformal Conic) grid conversion parameters.
_RE = 6371.00877
_GRID = 5.0
_SLAT1 = 30.0
_SLAT2 = 60.0
_OLON = 126.0
_OLAT = 38.0
_XO = 43
_YO = 136

_PTY_LABELS = {
    "0": "맑음",
    "1": "비",
    "2": "비/눈",
    "3": "눈",
    "5": "빗방울",
    "6": "빗방울눈날림",
    "7": "눈날림",
}


class ForecastUnavailable(Exception):
    """Raised when KMA's forecast can't be reached, parsed, or has nothing
    for the requested date. Callers should fall back to a 404."""


def latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    """Convert lat/lon (decimal degrees) to KMA's LCC forecast grid (nx, ny)."""
    degrad = math.pi / 180.0
    re = _RE / _GRID
    slat1 = _SLAT1 * degrad
    slat2 = _SLAT2 * degrad
    olon = _OLON * degrad
    olat = _OLAT * degrad

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = (sf**sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / (ro**sn)

    ra = math.tan(math.pi * 0.25 + lat * degrad * 0.5)
    ra = re * sf / (ra**sn)
    theta = lon * degrad - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    x = int(ra * math.sin(theta) + _XO + 0.5)
    y = int(ro - ra * math.cos(theta) + _YO + 0.5)
    return x, y


CORRIDOR_NX, CORRIDOR_NY = 60, 127


def precipitation_label(pty_code: str) -> str:
    """Human-readable label for a raw PTY code. Unknown codes pass through as-is."""
    return _PTY_LABELS.get(pty_code, pty_code)


def is_precipitating(pty_code: str) -> bool:
    """맑음/강수 이진 분류(모델 입력용). PTY != "0"이면 강수."""
    return pty_code != "0"


def _service_key() -> str:
    raw = os.environ.get("KMA_FORECAST_API_KEY")
    if not raw:
        raise ForecastUnavailable("KMA_FORECAST_API_KEY is not set")
    return unquote(raw)


def _latest_base_datetime(now: datetime | None = None) -> tuple[str, str]:
    """The most recently published base_date/base_time (YYYYMMDD, HHMM)."""
    now = now or datetime.now()
    published = [
        now.replace(hour=int(base_time[:2]), minute=0, second=0, microsecond=0)
        for base_time in _BASE_TIMES
        if now.replace(hour=int(base_time[:2]), minute=0, second=0, microsecond=0)
        + timedelta(minutes=_BASE_TIME_PUBLISH_DELAY_MIN)
        <= now
    ]
    latest = (
        max(published)
        if published
        else ((now - timedelta(days=1)).replace(hour=23, minute=0, second=0, microsecond=0))
    )
    return latest.strftime("%Y%m%d"), latest.strftime("%H%M")


def fetch_forecast_items(
    nx: int = CORRIDOR_NX,
    ny: int = CORRIDOR_NY,
    timeout: float = DEFAULT_TIMEOUT,
    now: datetime | None = None,
) -> list[dict[str, str]]:
    """Fetch every (category, fcstDate, fcstTime, fcstValue) row for one grid
    cell's latest published forecast, cached for _CACHE_TTL_SECONDS."""
    base_date, base_time = _latest_base_datetime(now)
    cache_key = (base_date, base_time, nx, ny)
    cached = _cache.get(cache_key)
    if cached is not None:
        cached_at, items = cached
        if time.monotonic() - cached_at < _CACHE_TTL_SECONDS:
            return items

    try:
        response = _client.get(
            FORECAST_URL,
            params={
                "serviceKey": _service_key(),
                "pageNo": "1",
                "numOfRows": "1000",
                "dataType": "JSON",
                "base_date": base_date,
                "base_time": base_time,
                "nx": str(nx),
                "ny": str(ny),
            },
            timeout=timeout,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ForecastUnavailable(f"KMA forecast request failed: {exc}") from exc

    try:
        body = response.json()
        header = body["response"]["header"]
        if header["resultCode"] != "00":
            raise ForecastUnavailable(
                f"KMA forecast returned resultCode={header['resultCode']}: "
                f"{header.get('resultMsg')}"
            )
        items = body["response"]["body"]["items"]["item"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ForecastUnavailable(f"KMA forecast response was not parseable: {exc}") from exc

    _cache[cache_key] = (time.monotonic(), items)
    return items


@dataclass
class DailyForecast:
    """One date's forecast, reduced to what /stops/{id}/context needs."""

    date: int
    temperature: float
    high_temp: float
    humidity: float
    wind_speed: float
    precipitation_type: str
    is_precipitating: bool


def _nearest_time_value(
    items: list[dict[str, str]], category: str, target_date: str, now: datetime
) -> str | None:
    """The category's forecast value at the time slot closest to now, on target_date."""
    same_day = [
        item
        for item in items
        if item.get("category") == category and item.get("fcstDate") == target_date
    ]
    if not same_day:
        return None
    now_minutes = now.hour * 60 + now.minute

    def _distance(item: dict[str, str]) -> int:
        fcst_time = item["fcstTime"]
        return abs(int(fcst_time[:2]) * 60 + int(fcst_time[2:]) - now_minutes)

    return min(same_day, key=_distance)["fcstValue"]


def build_daily_forecast(
    items: list[dict[str, str]], target_date: int, now: datetime | None = None
) -> DailyForecast:
    """Reduce a fetch_forecast_items() response to one date's DailyForecast."""
    now = now or datetime.now()
    date_str = str(target_date)

    temp_raw = _nearest_time_value(items, "TMP", date_str, now)
    humidity_raw = _nearest_time_value(items, "REH", date_str, now)
    wind_raw = _nearest_time_value(items, "WSD", date_str, now)
    pty_raw = _nearest_time_value(items, "PTY", date_str, now)
    if temp_raw is None or humidity_raw is None or wind_raw is None or pty_raw is None:
        raise ForecastUnavailable(f"no forecast for date {target_date} in the fetched window")

    high_temp_raw = next(
        (
            item["fcstValue"]
            for item in items
            if item.get("category") == "TMX" and item.get("fcstDate") == date_str
        ),
        None,
    )
    if high_temp_raw is not None:
        high_temp = float(high_temp_raw)
    else:
        same_day_tmp = [
            float(item["fcstValue"])
            for item in items
            if item.get("category") == "TMP" and item.get("fcstDate") == date_str
        ]
        if not same_day_tmp:
            raise ForecastUnavailable(f"no TMX/TMP for date {target_date} in the fetched window")
        high_temp = max(same_day_tmp)

    return DailyForecast(
        date=target_date,
        temperature=float(temp_raw),
        high_temp=high_temp,
        humidity=float(humidity_raw),
        wind_speed=float(wind_raw),
        precipitation_type=precipitation_label(pty_raw),
        is_precipitating=is_precipitating(pty_raw),
    )
