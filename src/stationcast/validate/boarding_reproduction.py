"""Daily boarding reproduction error (issue #16, items 3-4: MAPE + sensitivity).

Re-scopes "승차 재현 MAPE" for the post-pivot pipeline: the wait estimator
(estimator/wait_population.py) takes real per-route boarding as a direct
input rather than predicting it, so there is nothing for a MAPE against the
estimator's own output to measure (see review discussion, issue #16).

What can be validated instead is the *demand characterization* that feeds
the whole pipeline: how well a single per-stop "typical day" boarding
figure reproduces real day-to-day boarding (corridor_daily.parquet, 3
years), and how much the weekday/weather/temperature correction factors
(features/demand_factors.py) actually improve that reproduction.

Both predictions are fit on a 2-year train split and evaluated only on the
held-out final year (TRAIN_TEST_CUTOFF) rather than on the same days they
were fit from. Fitting and evaluating on the same days would let each
day's own value leak into its own prediction (the correction factors are
just group means over corridor_daily), which systematically understates
the real reproduction error (see issue #16 review discussion):

1. 무보정: each stop's train-period daily mean boarding.
2. 요일+날씨+기온보정: weekday_weather_factor's 12-group train mean.

Only weekday_weather_factor.parquet's 12-group correction is used, not
weekday_holiday_factor.parquet's 2-group (요일구분 only) correction --
weekday_weather_factor's grouping already includes 요일구분 as one of its
three axes, so it's a strict superset and the 2-group table adds nothing
a comparison against it wouldn't already show (see review discussion,
issue #16; also noted in data/README.md §11).
"""

from pathlib import Path

import pandas as pd

from stationcast.features.demand_factors import build_weekday_weather_factor, factor_column_name

TRAIN_TEST_CUTOFF = 20250701
"""First 사용일자 of the held-out test year. Correction factors are fit on
days before this (2023-07-01~2025-06-30, ~2 years) and evaluated against
actual boarding on/after this date (2025-07-01~2026-06-30, ~1 year), so
MAPE measures reproduction on days the factors never saw."""

STOP_COLLAPSE_RATIO = 0.1
"""A stop counts as "collapsed" on a date when its 승차 falls below this
fraction of that stop's own median day. Per-stop rather than corridor-wide
so the test means the same thing for a 4-boardings-a-day side street and a
2,000-boardings 종로 stop."""

ANOMALY_THRESHOLD = 0.15
"""A date where at least this fraction of stops collapsed
(STOP_COLLAPSE_RATIO) is treated as a day the bus network did not run. The
collapsed stops' rows for that date are dropped before fitting or evaluating
either prediction; stops that ran normally keep the date (_anomalous_stop_days).

Discovered via 2026-01-13/2026-01-14, the two-day Seoul city-bus strike
(data/README.md §10). This started out as a rule on the corridor-wide
*total* (below 10% of the median day), which worked at demo scope -- the
21-stop corridor is served by 간선/지선 only, so it collapsed to 1% of
normal. It silently stops working at STATIONCAST_SCOPE=seoul: 마을버스 is
outside 준공영제, kept running, and carried ~40% more riders, so the
citywide total only fell to 26% of the median -- above a 10% cutoff, and
uncomfortably close to the 33% of the quietest 설날 day, leaving no safe
threshold on totals at all.

Counting collapsed *stops* separates the two cleanly, because a strike and
a holiday have different shapes: a holiday makes everyone somewhat quieter,
while a strike zeroes out the 간선/지선 stops and leaves 마을버스 stops
untouched. Measured over 서울 전체:

    2026-01-13 (파업)   28.7%
    2026-01-14 (파업)   25.4%
    2024-02-10 (설날)    7.5%
    2025-01-29 (설날)    6.7%
    2025-10-06 (추석)    6.1%
    평범한 날            1.0%

0.15 sits between 7.5% and 25.4% with roughly 1.7x headroom either way,
against the 26%-vs-33% squeeze the totals rule offered. The same rule still
fires at demo scope, where a strike day collapses nearly every stop, so
both scopes share one definition."""


_DAY_TYPES = ("평일", "주말+공휴일")
_WEATHER_TYPES = ("맑음", "강수")
_TEMP_TYPES = ("저온", "보통", "고온")


def _anomalous_stop_days(
    corridor_daily: pd.DataFrame, threshold: float = ANOMALY_THRESHOLD
) -> pd.MultiIndex:
    """(표준버스정류장ID, 사용일자) pairs to drop: stops that collapsed, on dates
    where enough stops collapsed to mark a network-wide event.

    Both halves matter. Without the date gate, every stop's ordinary quiet day
    would qualify -- stops whose median is under 5 boardings collapse on 12.99%
    of days just from noise. Without the per-stop half, one date's event takes
    every stop down with it, which is wrong whenever the event is local: the
    21-stop demo corridor sits on 종로/보신각, so 2023-12-31's 제야의 종 road
    closures collapsed 23.81% of *it* (5 stops) and tripped the gate, while
    citywide the same day is 3.78% and never qualifies. The other 16 corridor
    stops ran normally that night and keep the date.
    """
    stop_medians = corridor_daily.groupby("표준버스정류장ID")["승차"].median()
    floors = corridor_daily["표준버스정류장ID"].map(stop_medians) * STOP_COLLAPSE_RATIO
    collapsed = corridor_daily["승차"] < floors
    event_day = collapsed.groupby(corridor_daily["사용일자"]).transform("mean") >= threshold
    dropped = corridor_daily[collapsed & event_day]
    return pd.MultiIndex.from_frame(dropped[["표준버스정류장ID", "사용일자"]])


def _drop_stop_days(frame: pd.DataFrame, stop_days: pd.MultiIndex) -> pd.DataFrame:
    keys = pd.MultiIndex.from_frame(frame[["표준버스정류장ID", "사용일자"]])
    return frame[~keys.isin(stop_days)]


def _long_group_means(
    weather_factor: pd.DataFrame, value_prefix: str, out_col: str
) -> pd.DataFrame:
    """Melt a wide {value_prefix}_{day}_{weather}_{temp} block into long form.

    Builds each group's column name with factor_column_name() (issue #105)
    instead of reverse-parsing it back out of the melted column label (issue
    #110) -- the 12-group label set is fixed and known here, so there is
    nothing to infer from the string.
    """
    groups = []
    for day in _DAY_TYPES:
        for weather in _WEATHER_TYPES:
            for temp in _TEMP_TYPES:
                column = factor_column_name(value_prefix, day, weather, temp)
                if column not in weather_factor.columns:
                    continue
                group = weather_factor[["표준버스정류장ID", "정류장명", column]].rename(
                    columns={column: out_col}
                )
                group["요일구분"] = day
                group["날씨구분"] = weather
                group["기온구분"] = temp
                groups.append(group)
    return pd.concat(groups, ignore_index=True)


def build_boarding_reproduction_report(
    corridor_daily: pd.DataFrame,
    features_daily: pd.DataFrame,
) -> pd.DataFrame:
    """Per (stop, test-day) actual boarding vs two train-fit predictions.

    corridor_daily: 표준버스정류장ID, 정류장명, 사용일자, 승차, 하차 (3-year real series).
    features_daily: corridor_daily joined with 요일구분/날씨구분/기온구분 labels
        (features/demand_factors.py's build_features_daily output).

    Both inputs cover the full 3-year range; this function drops
    ANOMALY_THRESHOLD-flagged dates first, splits the remainder at
    TRAIN_TEST_CUTOFF, fits both predictions on the train split only, and
    returns one row per (stop, day) for the test split only, with 실측_승차
    and the two predictions, ready for MAPE aggregation.
    """
    anomalies = _anomalous_stop_days(corridor_daily)
    corridor_daily = _drop_stop_days(corridor_daily, anomalies)
    features_daily = _drop_stop_days(features_daily, anomalies)

    train_daily = corridor_daily[corridor_daily["사용일자"] < TRAIN_TEST_CUTOFF]
    train_features = features_daily[features_daily["사용일자"] < TRAIN_TEST_CUTOFF]
    test_features = features_daily[features_daily["사용일자"] >= TRAIN_TEST_CUTOFF]

    overall_mean = (
        train_daily.groupby(["표준버스정류장ID", "정류장명"])["승차"]
        .mean()
        .rename("무보정_예측승차")
        .reset_index()
    )

    weekday_weather_factor = build_weekday_weather_factor(train_features)
    full_means = _long_group_means(weekday_weather_factor, "평균승차", "요일날씨기온보정_예측승차")

    merged = test_features.merge(overall_mean, on=["표준버스정류장ID", "정류장명"], how="left")
    merged = merged.merge(
        full_means,
        on=["표준버스정류장ID", "정류장명", "요일구분", "날씨구분", "기온구분"],
        how="left",
    )

    cols = [
        "표준버스정류장ID",
        "정류장명",
        "사용일자",
        "요일구분",
        "날씨구분",
        "기온구분",
        "승차",
        "무보정_예측승차",
        "요일날씨기온보정_예측승차",
    ]
    return (
        merged[cols]
        .rename(columns={"승차": "실측_승차"})
        .sort_values(["표준버스정류장ID", "사용일자"])
        .reset_index(drop=True)
    )


def _mape(actual: pd.Series, predicted: pd.Series) -> float:
    """Mean absolute percentage error, excluding zero-actual rows (undefined %)."""
    valid = actual > 0
    return float(((predicted[valid] - actual[valid]).abs() / actual[valid]).mean() * 100)


MAPE_VOLUME_FLOOR = 100
"""Daily 승차 a (stop, day) must reach to enter the floored MAPE figures.

MAPE divides by the actual, so it is meaningless where the actual is a
handful of people: predicting 12 at a stop that saw 4 is an 8-person miss
and a 200% error, while the same 8-person miss at a 400-boarding stop is
2%. The 21-stop demo corridor is all downtown arterials and never exercised
this, but 서울 전체 is mostly small stops, and they dominate the unfiltered
mean -- measured over the held-out year, by decile of actual boarding:

    decile 1 (median   4/day)   297.2%
    decile 2 (median  19/day)    56.4%
    decile 5 (median 181/day)    16.3%
    decile 8 (median 741/day)    11.5%
    decile 10 (median 1611/day)  10.0%

Both figures are reported rather than just the floored one: the unfiltered
number is the honest headline, and the floored number is what is comparable
to the demo corridor's, which sat entirely in the top deciles."""


def summarize_mape(report: pd.DataFrame, volume_floor: int = MAPE_VOLUME_FLOOR) -> dict[str, float]:
    """Corridor-wide MAPE for each prediction version, unfiltered and volume-floored.

    The _100이상 variants restrict to (stop, day) rows with at least
    ``volume_floor`` actual boardings -- see MAPE_VOLUME_FLOOR for why the
    unfiltered mean stops being informative at 서울 전체 scope.
    """
    busy = report[report["실측_승차"] >= volume_floor]
    return {
        "무보정_MAPE": _mape(report["실측_승차"], report["무보정_예측승차"]),
        "요일날씨기온보정_MAPE": _mape(report["실측_승차"], report["요일날씨기온보정_예측승차"]),
        f"무보정_MAPE_{volume_floor}이상": _mape(busy["실측_승차"], busy["무보정_예측승차"]),
        f"요일날씨기온보정_MAPE_{volume_floor}이상": _mape(
            busy["실측_승차"], busy["요일날씨기온보정_예측승차"]
        ),
    }


def per_stop_mape(report: pd.DataFrame) -> pd.DataFrame:
    """Per-stop MAPE for each version, for the sensitivity/percentile breakdown."""
    rows = []
    for (stop_id, name), group in report.groupby(["표준버스정류장ID", "정류장명"], sort=False):
        rows.append(
            {
                "표준버스정류장ID": stop_id,
                "정류장명": name,
                "무보정_MAPE": _mape(group["실측_승차"], group["무보정_예측승차"]),
                "요일날씨기온보정_MAPE": _mape(
                    group["실측_승차"], group["요일날씨기온보정_예측승차"]
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("표준버스정류장ID").reset_index(drop=True)


def run(processed_dir: Path, out_dir: Path) -> None:
    corridor_daily = pd.read_parquet(processed_dir / "corridor_daily.parquet")
    features_daily = pd.read_parquet(processed_dir / "corridor_features_daily.parquet")

    anomalies = _anomalous_stop_days(corridor_daily)
    if len(anomalies):
        dates = sorted({int(date) for _, date in anomalies})
        print(f"이상치로 제외된 (정류장, 날짜) {len(anomalies):,}쌍 "
              f"(ANOMALY_THRESHOLD={ANOMALY_THRESHOLD}), 해당 날짜: {dates}")

    report = build_boarding_reproduction_report(corridor_daily, features_daily)
    summary = summarize_mape(report)
    by_stop = per_stop_mape(report)

    out_dir.mkdir(parents=True, exist_ok=True)
    report.to_parquet(out_dir / "boarding_reproduction_report.parquet", index=False)
    by_stop.to_csv(out_dir / "boarding_reproduction_by_stop.csv", index=False, encoding="utf-8-sig")

    print(f"=== 승차 재현 MAPE ({TRAIN_TEST_CUTOFF} 이후 held-out 1년 기준) ===")
    for k, v in summary.items():
        print(f"{k}: {v:.1f}%")


if __name__ == "__main__":
    run(Path("data/processed"), Path("data/processed"))
