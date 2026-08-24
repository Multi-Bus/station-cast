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
    start: int | None = CORRIDOR_START,
    end: int | None = CORRIDOR_END,
) -> pd.DataFrame:
    """Filter to a date range and collapse same-day holidays into one row.

    Some dates carry more than one entry (e.g., 20250505 is both 어린이날
    and 부처님오신날); these are combined into a single row per date so
    the result joins 1:1 against corridor_daily/weather_daily on 사용일자.

    start/end=None disables that bound -- used for the /stops/{id}/context
    serving path (holiday_daily_all.parquet), which needs "오늘" and
    near-future dates past the training corridor's CORRIDOR_END.
    """
    sub = raw_df.copy()
    sub = sub[sub["isHoliday"] == "Y"]
    sub["locdate"] = sub["locdate"].astype(int)
    if start is not None:
        sub = sub[sub["locdate"] >= start]
    if end is not None:
        sub = sub[sub["locdate"] <= end]

    grouped = (
        sub.groupby("locdate")["dateName"]
        .apply(lambda names: "·".join(names))
        .reset_index()
        .rename(columns={"locdate": "사용일자", "dateName": "공휴일명"})
    )
    return grouped.sort_values("사용일자").reset_index(drop=True)


def run(csv_path: Path, out_dir: Path) -> None:
    """Build both holiday parquet outputs from the raw 특일정보 API dump.

    holiday_daily.parquet stays corridor-range-bounded (training input,
    joined against corridor_daily/weather_daily). holiday_daily_all.parquet
    is unbounded -- api/data.py reads this one for /stops/{id}/context's
    day-type check, which needs today/near-future dates.
    """
    raw = load_raw_holidays(csv_path)
    daily = build_holiday_daily(raw)
    daily_all = build_holiday_daily(raw, start=None, end=None)

    out_dir.mkdir(parents=True, exist_ok=True)
    daily.to_parquet(out_dir / "holiday_daily.parquet", index=False)
    daily_all.to_parquet(out_dir / "holiday_daily_all.parquet", index=False)


if __name__ == "__main__":
    run(Path("data/raw/holidays.csv"), Path("data/processed"))
