"""Public holiday collector (한국천문연구원 특일정보 API, getRestDeInfo).

Filters the raw API dump (data/raw/SPCDE_HOLIDAY_2023_2026.csv, fetched
for solYear 2023-2026) down to the corridor's date range and collapses
same-day co-occurring holidays (e.g., 2025-05-05 is both 어린이날 and
부처님오신날) into one row per date. Weekends are computed directly from
the date in features/ (not fetched here); combined with this holiday
flag they form the "평일 vs 주말+공휴일" grouping for issue #10.
"""

from pathlib import Path

import pandas as pd

# 3-year corridor range (issue for the weather+weekday combined factor):
# extended from 1 year to 3 so the rarest weekday-type x weather x
# temperature combination (주말+공휴일 x 강수 x 기온구분) has enough
# samples. 2023-07 avoids Seoul's COVID-era social distancing, lifted
# 2022-04-18 -- data from before that skews ridership independent of
# weather.
CORRIDOR_START = 20230701
CORRIDOR_END = 20260630


def load_raw_holidays(csv_path: Path) -> pd.DataFrame:
    """Load the raw 특일정보 API dump (utf-8-sig encoded)."""
    return pd.read_csv(csv_path, encoding="utf-8-sig")


def build_holiday_daily(
    raw_df: pd.DataFrame,
    start: int = CORRIDOR_START,
    end: int = CORRIDOR_END,
) -> pd.DataFrame:
    """Filter to the corridor's date range and collapse same-day holidays.

    Some dates carry more than one entry (e.g., 20250505 is both 어린이날
    and 부처님오신날); these are combined into a single row per date so
    the result joins 1:1 against corridor_daily/weather_daily on 사용일자.
    """
    sub = raw_df.copy()
    sub["locdate"] = sub["locdate"].astype(int)
    sub = sub[(sub["locdate"] >= start) & (sub["locdate"] <= end)]

    grouped = (
        sub.groupby("locdate")["dateName"]
        .apply(lambda names: "·".join(names))
        .reset_index()
        .rename(columns={"locdate": "사용일자", "dateName": "공휴일명"})
    )
    return grouped.sort_values("사용일자").reset_index(drop=True)


def run(csv_path: Path, out_dir: Path) -> None:
    """Build holiday_daily.parquet from the raw 특일정보 API dump."""
    raw = load_raw_holidays(csv_path)
    daily = build_holiday_daily(raw)

    out_dir.mkdir(parents=True, exist_ok=True)
    daily.to_parquet(out_dir / "holiday_daily.parquet", index=False)


if __name__ == "__main__":
    run(Path("data/raw/holidays.csv"), Path("data/processed"))
