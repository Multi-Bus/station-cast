"""Daily boarding reproduction error (issue #16, items 3-4: MAPE + sensitivity).

Re-scopes "승차 재현 MAPE" for the post-pivot pipeline: the wait estimator
(estimator/wait_population.py) takes real per-route boarding as a direct
input rather than predicting it, so there is nothing for a MAPE against the
estimator's own output to measure (see review discussion, issue #16).

What can be validated instead is the *demand characterization* that feeds
the whole pipeline: how well a single per-stop "typical day" boarding
figure reproduces real day-to-day boarding (corridor_daily.parquet, 3
years), and how much the weekday/weather/temperature correction factors
(features/demand_factors.py) actually improve that reproduction. Three
progressively-corrected predictions give both the MAPE (item 3) and a
natural sensitivity comparison (item 4) from one analysis:

1. 무보정: each stop's overall 3-year daily mean boarding.
2. 요일보정: weekday_holiday_factor.parquet's 2-group (평일 / 주말+공휴일) mean.
3. 요일+날씨+기온보정: weekday_weather_factor.parquet's 12-group mean.
"""

from pathlib import Path

import pandas as pd

_TEMP_LABELS = ["저온", "보통", "고온"]

KNOWN_NIGHT_BUS_ONLY_DATES: tuple[int, ...] = (20260113, 20260114)
"""사용일자에서 해당 날짜에 그 정류장을 지나는 노선이 전부 심야버스뿐이라, 심야버스
제외 필터 적용 후 승차가 거의 0에 가깝게 남는 날(data/README.md §7에 문서화된 현상,
버그 아님). MAPE는 실측값이 0에 가까우면 퍼센트 오차가 발산하므로, 이 날짜들을 빼고
계산해야 그 왜곡 없이 "전형적인 하루" 재현력을 정직하게 잴 수 있다."""


def _long_group_means(
    weather_factor: pd.DataFrame, value_prefix: str, out_col: str
) -> pd.DataFrame:
    """Melt a wide {value_prefix}_{day}_{weather}_{temp} block into long form."""
    value_cols = [c for c in weather_factor.columns if c.startswith(f"{value_prefix}_")]
    long_df = weather_factor.melt(
        id_vars=["표준버스정류장ID", "정류장명"],
        value_vars=value_cols,
        var_name="_group",
        value_name=out_col,
    )
    parts = long_df["_group"].str.split("_", n=3, expand=True)
    long_df["요일구분"] = parts[1]
    long_df["날씨구분"] = parts[2]
    long_df["기온구분"] = parts[3]
    return long_df.drop(columns="_group")


def build_boarding_reproduction_report(
    corridor_daily: pd.DataFrame,
    features_daily: pd.DataFrame,
    weekday_holiday_factor: pd.DataFrame,
    weekday_weather_factor: pd.DataFrame,
) -> pd.DataFrame:
    """Per (stop, day) actual boarding vs three progressively-corrected predictions.

    corridor_daily: 표준버스정류장ID, 정류장명, 사용일자, 승차, 하차 (3-year real series).
    features_daily: corridor_daily joined with 요일구분/날씨구분/기온구분 labels
        (features/demand_factors.py's build_features_daily output).
    weekday_holiday_factor: features/demand_factors.py's 2-group (요일구분 only) output.
    weekday_weather_factor: features/demand_factors.py's 12-group output.

    Returns one row per (stop, day) with 실측_승차 and the three predictions,
    ready for MAPE aggregation.
    """
    overall_mean = (
        corridor_daily.groupby(["표준버스정류장ID", "정류장명"])["승차"]
        .mean()
        .rename("무보정_예측승차")
        .reset_index()
    )

    holiday_means = weekday_holiday_factor.melt(
        id_vars=["표준버스정류장ID", "정류장명"],
        value_vars=["평균승차_평일", "평균승차_주말+공휴일"],
        var_name="_group",
        value_name="요일보정_예측승차",
    )
    holiday_means["요일구분"] = holiday_means["_group"].str.removeprefix("평균승차_")
    holiday_means = holiday_means.drop(columns="_group")

    full_means = _long_group_means(weekday_weather_factor, "평균승차", "요일날씨기온보정_예측승차")

    merged = features_daily.merge(overall_mean, on=["표준버스정류장ID", "정류장명"], how="left")
    merged = merged.merge(
        holiday_means, on=["표준버스정류장ID", "정류장명", "요일구분"], how="left"
    )
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
        "요일보정_예측승차",
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
    """Corridor-wide MAPE for each of the three prediction versions.

    A single near-zero 실측_승차 day makes MAPE's percentage error diverge
    (e.g. 종로3가.탑골공원 on 2026-01-14: 실측 2명 vs 예측 ~3,345명 is a
    162,291% error, alone worth +148pp on that stop's 1,096-day average).
    KNOWN_NIGHT_BUS_ONLY_DATES excludes the specific dates this happens on
    (documented, not a silent data-cleaning choice) by default; pass
    ``exclude_known_anomalies=False`` to see the raw, undistorted-view MAPE.
    """
    if exclude_known_anomalies:
        report = _exclude_known_anomalies(report)
    return {
        "무보정_MAPE": _mape(report["실측_승차"], report["무보정_예측승차"]),
        "요일보정_MAPE": _mape(report["실측_승차"], report["요일보정_예측승차"]),
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
                "요일보정_MAPE": _mape(group["실측_승차"], group["요일보정_예측승차"]),
                "요일날씨기온보정_MAPE": _mape(
                    group["실측_승차"], group["요일날씨기온보정_예측승차"]
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("표준버스정류장ID").reset_index(drop=True)


def run(processed_dir: Path, out_dir: Path) -> None:
    corridor_daily = pd.read_parquet(processed_dir / "corridor_daily.parquet")
    features_daily = pd.read_parquet(processed_dir / "corridor_features_daily.parquet")
    weekday_holiday_factor = pd.read_parquet(processed_dir / "weekday_holiday_factor.parquet")
    weekday_weather_factor = pd.read_parquet(processed_dir / "weekday_weather_factor.parquet")

    report = build_boarding_reproduction_report(
        corridor_daily, features_daily, weekday_holiday_factor, weekday_weather_factor
    )
    summary_raw = summarize_mape(report, exclude_known_anomalies=False)
    summary = summarize_mape(report, exclude_known_anomalies=True)
    by_stop = per_stop_mape(report)

    out_dir.mkdir(parents=True, exist_ok=True)
    report.to_parquet(out_dir / "boarding_reproduction_report.parquet", index=False)
    by_stop.to_csv(out_dir / "boarding_reproduction_by_stop.csv", index=False, encoding="utf-8-sig")

    print(f"=== 승차 재현 MAPE (원본, {KNOWN_NIGHT_BUS_ONLY_DATES} 포함) ===")
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
