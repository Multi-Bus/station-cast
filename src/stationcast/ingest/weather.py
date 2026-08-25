"""Daily weather (KMA ASOS) collector.

Provides a single Seoul-station daily weather series (temperature,
precipitation, humidity, snowfall, wind) covering the same date range as
corridor_daily.parquet, for issue #10's weekday/holiday/weather
correction factors. Already at single-location daily granularity, so no
stop filtering or route aggregation is needed here -- only column
selection and cleanup.
"""

from pathlib import Path

import pandas as pd

from stationcast.ingest._common import read_cp949_csv

_COLUMN_MAP = {
    "일시": "사용일자",
    "평균기온(°C)": "평균기온",
    "최고기온(°C)": "최고기온",
    "최저기온(°C)": "최저기온",
    "일강수량(mm)": "강수량",
    "평균 상대습도(%)": "습도",
    "일 최심신적설(cm)": "신적설",
    "평균 풍속(m/s)": "평균풍속",
    "최대 풍속(m/s)": "최대풍속",
}

# KMA convention: these are NaN when the event didn't occur that day
# (no rain / no new snow), not missing measurements.
_ZERO_FILL_COLUMNS = ("강수량", "신적설")


def load_daily_weather(csv_path: Path) -> pd.DataFrame:
    """Load the raw KMA ASOS daily CSV (cp949-encoded)."""
    return read_cp949_csv(csv_path)


def build_weather_daily(weather_df: pd.DataFrame) -> pd.DataFrame:
    """Select and clean the columns relevant to ridership behavior.

    ``사용일자`` is converted to the same int(YYYYMMDD) form used by
    corridor_daily.parquet (built by oa12912.py) so the two can be
    joined directly on that column.
    """
    selected = weather_df[list(_COLUMN_MAP.keys())].rename(columns=_COLUMN_MAP)
    selected["사용일자"] = pd.to_datetime(selected["사용일자"]).dt.strftime("%Y%m%d").astype(int)
    zero_fill = list(_ZERO_FILL_COLUMNS)
    selected[zero_fill] = selected[zero_fill].fillna(0.0)
    return selected.sort_values("사용일자").reset_index(drop=True)


def run(csv_path: Path, out_dir: Path) -> None:
    """Build weather_daily.parquet from a raw KMA ASOS daily CSV."""
    raw = load_daily_weather(csv_path)
    daily = build_weather_daily(raw)

    out_dir.mkdir(parents=True, exist_ok=True)
    daily.to_parquet(out_dir / "weather_daily.parquet", index=False)


if __name__ == "__main__":
    run(Path("data/raw/weather.csv"), Path("data/processed"))
