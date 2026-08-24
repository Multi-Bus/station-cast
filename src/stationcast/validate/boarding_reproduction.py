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
issue #16; also noted in data/README.md §8).
"""

from pathlib import Path

import pandas as pd

from stationcast.features.demand_factors import build_weekday_weather_factor, factor_column_name

TRAIN_TEST_CUTOFF = 20250701
"""First 사용일자 of the held-out test year. Correction factors are fit on
days before this (2023-07-01~2025-06-30, ~2 years) and evaluated against
actual boarding on/after this date (2025-07-01~2026-06-30, ~1 year), so
MAPE measures reproduction on days the factors never saw."""

KNOWN_NIGHT_BUS_ONLY_DATES: tuple[int, ...] = (20260113, 20260114)
"""Dates where every route passing the stop was night-bus-only, so boarding
drops to near zero after the night-bus exclusion filter (documented,
pre-existing phenomenon -- see data/README.md §7, not a bug). MAPE diverges
when the actual value is near zero, so excluding these dates is necessary to
get an honest read on "typical day" reproduction without that distortion."""


_DAY_TYPES = ("평일", "주말+공휴일")
_WEATHER_TYPES = ("맑음", "강수")
_TEMP_TYPES = ("저온", "보통", "고온")


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

    Both inputs cover the full 3-year range; this function splits them at
    TRAIN_TEST_CUTOFF itself, fits both predictions on the train split
    only, and returns one row per (stop, day) for the test split only, with
    실측_승차 and the two predictions, ready for MAPE aggregation.
    """
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
    return merged[cols].rename(columns={"승차": "실측_승차"}).sort_values(
        ["표준버스정류장ID", "사용일자"]
    ).reset_index(drop=True)


def _mape(actual: pd.Series, predicted: pd.Series) -> float:
    """Mean absolute percentage error, excluding zero-actual rows (undefined %)."""
    valid = actual > 0
    return float(((predicted[valid] - actual[valid]).abs() / actual[valid]).mean() * 100)


def _exclude_known_anomalies(report: pd.DataFrame) -> pd.DataFrame:
    return report[~report["사용일자"].isin(KNOWN_NIGHT_BUS_ONLY_DATES)]


def summarize_mape(report: pd.DataFrame, exclude_known_anomalies: bool = True) -> dict[str, float]:
    """Corridor-wide MAPE for each of the two prediction versions.

    A single near-zero 실측_승차 day makes MAPE's percentage error diverge
    (e.g. 종로3가.탑골공원 on 2026-01-14: 실측 2명 vs 예측 ~3,345명 is a
    162,291% error, alone worth a large share of that stop's test-period
    average). KNOWN_NIGHT_BUS_ONLY_DATES excludes the specific dates this
    happens on (documented, not a silent data-cleaning choice) by default;
    pass ``exclude_known_anomalies=False`` to see the raw, undistorted-view
    MAPE.
    """
    if exclude_known_anomalies:
        report = _exclude_known_anomalies(report)
    return {
        "무보정_MAPE": _mape(report["실측_승차"], report["무보정_예측승차"]),
        "요일날씨기온보정_MAPE": _mape(report["실측_승차"], report["요일날씨기온보정_예측승차"]),
    }


def per_stop_mape(report: pd.DataFrame, exclude_known_anomalies: bool = True) -> pd.DataFrame:
    """Per-stop MAPE for each version, for the sensitivity/percentile breakdown."""
    if exclude_known_anomalies:
        report = _exclude_known_anomalies(report)
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

    report = build_boarding_reproduction_report(corridor_daily, features_daily)
    summary_raw = summarize_mape(report, exclude_known_anomalies=False)
    summary = summarize_mape(report, exclude_known_anomalies=True)
    by_stop = per_stop_mape(report)

    out_dir.mkdir(parents=True, exist_ok=True)
    report.to_parquet(out_dir / "boarding_reproduction_report.parquet", index=False)
    by_stop.to_csv(out_dir / "boarding_reproduction_by_stop.csv", index=False, encoding="utf-8-sig")

    print(
        f"=== 승차 재현 MAPE (원본, {KNOWN_NIGHT_BUS_ONLY_DATES} 포함, "
        f"{TRAIN_TEST_CUTOFF} 이후 held-out 1년 기준) ==="
    )
    for k, v in summary_raw.items():
        print(f"{k}: {v:.1f}%")
    print()
    print(
        f"=== 승차 재현 MAPE ({KNOWN_NIGHT_BUS_ONLY_DATES} 제외, "
        "data/README.md §7 문서화된 이상치) ==="
    )
    for k, v in summary.items():
        print(f"{k}: {v:.1f}%")


if __name__ == "__main__":
    run(Path("data/processed"), Path("data/processed"))
