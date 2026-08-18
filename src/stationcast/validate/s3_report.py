"""S3 validation report: 제약 위반율 + 승차 재현 MAPE/민감도 (issue #16).

Combines physical_constraints.py's constraint-violation checks (item 1) with
boarding_reproduction.py's daily boarding MAPE and its built-in 3-step
sensitivity comparison (items 3-4) into one report. Item 2 (마감 잔차,
day-end closure residual) is intentionally omitted -- see the module
docstrings of physical_constraints.py and boarding_reproduction.py for why
it no longer applies under estimator/wait_population.py's per-hour,
no-carryover model.
"""

from pathlib import Path

import pandas as pd

from stationcast.validate.boarding_reproduction import (
    KNOWN_NIGHT_BUS_ONLY_DATES,
    build_boarding_reproduction_report,
    per_stop_mape,
    summarize_mape,
)
from stationcast.validate.physical_constraints import BUS_CAPACITY, build_validation_report


def build_report_markdown(
    constraint_summary: dict[str, float],
    mape_raw: dict[str, float],
    mape_clean: dict[str, float],
    by_stop: pd.DataFrame,
) -> str:
    """Render the combined S3 validation report as markdown."""
    lines = [
        "# S3 검증 리포트 — 제약 위반율 · 승차 재현 MAPE/민감도 (issue #16)",
        "",
        "## 1. 제약 위반율",
        "",
        f"- 비음수 위반율: {constraint_summary['비음수_위반율']:.1%}",
        f"- 용량 위반율 (버스 정원 {BUS_CAPACITY:.0f}명 가정): "
        f"{constraint_summary['용량_위반율']:.1%}",
        "",
        "`estimator/wait_population.py`(Little's Law)는 승차×배차간격이라는 항상 "
        "비음수인 곱으로 W를 계산하므로 비음수 위반은 구조상 발생하지 않는다. "
        "용량 위반율은 실측 승차가 '모든 버스가 빈 채로 도착한다'는 가정의 이론적 "
        "최대치를 넘는 (정류장,노선,시간대) 비율이다.",
        "",
        "## 2. 마감 잔차 — 해당 없음",
        "",
        "이전 큐 수지 모델은 대기인원이 하루 동안 누적되다 막차 시각에 "
        "0에 가깝게 닫히는지(마감 잔차)를 검증했다. `wait_population.py`는 매 "
        "시간대의 W(s,t)를 그 시간대의 실측 승차만으로 독립적으로 계산하고 "
        "이월(reservoir) 항 자체가 없으므로, 마감 잔차라는 개념이 성립하지 않는다"
        "(`physical_constraints.py` 모듈 docstring 참고). 이 항목은 리포트에서 "
        "제외하기로 결정했다.",
        "",
        "## 3~4. 승차 재현 MAPE 및 민감도 분석",
        "",
        "'모델이 승차를 예측'하는 지표가 아니다. 새 추정기는 실측 승차를 그대로 "
        "입력으로 쓰며, 승차 자체를 추정하지 않는다. 대신 이 코리더 전체 파이프라인이 "
        "기대는 '정류장별 평균적인 하루' 승차 특성화(`features/demand_factors.py`)가 "
        "실제 일별 승차(3년치, `corridor_daily.parquet`)를 얼마나 잘 재현하는지를 잰다. "
        "보정 단계를 하나씩 추가하며 MAPE가 얼마나 개선되는지가 곧 민감도 분석이다.",
        "",
        f"**알려진 이상치**: {KNOWN_NIGHT_BUS_ONLY_DATES}는 해당 코리더 노선이 "
        "그 날 사실상 심야버스뿐이라 심야버스 제외 필터 적용 후 실측 승차가 "
        "0에 가깝게 남는, `data/README.md` §7에 이미 문서화된 현상이다(계산 이후에 "
        "결과를 보고 정한 기준이 아니다). MAPE는 실측값이 0에 가까우면 퍼센트 오차가 "
        "발산하므로, 이 날짜들을 제외한 값을 기본으로 쓰고 원본 값도 함께 남긴다.",
        "",
        "| 보정 단계 | MAPE (원본, 이상치 포함) | MAPE (이상치 제외) |",
        "|---|---|---|",
        f"| 무보정 (정류장 3년 전체 평균) | {mape_raw['무보정_MAPE']:.1f}% "
        f"| {mape_clean['무보정_MAPE']:.1f}% |",
        f"| 요일 보정 (평일/주말+공휴일, 2그룹) | {mape_raw['요일보정_MAPE']:.1f}% "
        f"| {mape_clean['요일보정_MAPE']:.1f}% |",
        f"| 요일+날씨+기온 보정 (12그룹) | {mape_raw['요일날씨기온보정_MAPE']:.1f}% "
        f"| {mape_clean['요일날씨기온보정_MAPE']:.1f}% |",
        "",
        f"이상치를 제외한 최종(요일+날씨+기온 보정) MAPE는 코리더 평균 "
        f"**{mape_clean['요일날씨기온보정_MAPE']:.1f}%**이며, 21개 정류장 개별 범위는 "
        f"{by_stop['요일날씨기온보정_MAPE'].min():.1f}%~{by_stop['요일날씨기온보정_MAPE'].max():.1f}%"
        f"(중앙값 {by_stop['요일날씨기온보정_MAPE'].median():.1f}%)다.",
        "",
        "### 정류장별 상세",
        "",
        "| 정류장명 | 무보정 | 요일보정 | 요일+날씨+기온보정 |",
        "|---|---|---|---|",
    ]
    for _, row in by_stop.sort_values("요일날씨기온보정_MAPE").iterrows():
        lines.append(
            f"| {row['정류장명']} | {row['무보정_MAPE']:.1f}% | {row['요일보정_MAPE']:.1f}% "
            f"| {row['요일날씨기온보정_MAPE']:.1f}% |"
        )

    return "\n".join(lines) + "\n"


def run(processed_dir: Path, out_dir: Path, report_path: Path) -> None:
    """out_dir gets the regenerable CSV/parquet byproducts (gitignored, like
    the rest of data/processed/); report_path is the tracked markdown
    deliverable itself (e.g. docs/s3_validation_report.md)."""
    wait_df = pd.read_parquet(processed_dir / "corridor_wait.parquet")
    route_hourly = pd.read_parquet(processed_dir / "corridor_route_hourly.parquet")
    route_schedule = pd.read_parquet(processed_dir / "corridor_route_schedule.parquet")
    constraint_summary = build_validation_report(wait_df, route_hourly, route_schedule)

    corridor_daily = pd.read_parquet(processed_dir / "corridor_daily.parquet")
    features_daily = pd.read_parquet(processed_dir / "corridor_features_daily.parquet")
    weekday_holiday_factor = pd.read_parquet(processed_dir / "weekday_holiday_factor.parquet")
    weekday_weather_factor = pd.read_parquet(processed_dir / "weekday_weather_factor.parquet")
    report = build_boarding_reproduction_report(
        corridor_daily, features_daily, weekday_holiday_factor, weekday_weather_factor
    )
    mape_raw = summarize_mape(report, exclude_known_anomalies=False)
    mape_clean = summarize_mape(report, exclude_known_anomalies=True)
    by_stop = per_stop_mape(report)

    out_dir.mkdir(parents=True, exist_ok=True)
    by_stop.to_csv(out_dir / "boarding_reproduction_by_stop.csv", index=False, encoding="utf-8-sig")
    report.to_parquet(out_dir / "boarding_reproduction_report.parquet", index=False)

    markdown = build_report_markdown(constraint_summary, mape_raw, mape_clean, by_stop)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(markdown, encoding="utf-8")
    print(f"리포트 저장: {report_path}")
    print()
    print(markdown)


if __name__ == "__main__":
    run(Path("data/processed"), Path("data/processed"), Path("docs/s3_validation_report.md"))
