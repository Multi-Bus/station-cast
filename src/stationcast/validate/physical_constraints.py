"""Physical constraint checking — non-negativity and day-end closure (S1, issue #5).

Quantifies how well an estimator's W(s,t) output satisfies the two physical
constraints scoped to this issue:

- Non-negativity: W(s,t) >= 0 (a waiting population can't be negative).
- Day-end closure: W(s, last_hour) ~= 0 (a stop should empty out by day's end).

Capacity constraint and transfer consistency (the other two constraints from
the original design, see 개발계획_최종.md §2) are intentionally out of scope
here -- capacity would require per-vehicle seat data not present in
OA-12913's stop-hour aggregates, and transfer consistency requires lagged
time-series analysis. Both are deliberately deferred, not forgotten.

This module only measures violations; it does not judge whether a rate is
"acceptable". Reducing these numbers is S2 (calibrating transfer_rate and
arrival_rate in estimator/) work, and reporting them for real is S3
(issue #16).
"""

from pathlib import Path

import pandas as pd


def non_negativity_violation_rate(wait_df: pd.DataFrame) -> float:
    """Fraction of (stop, hour) rows where W < 0, across the whole corridor."""
    if len(wait_df) == 0:
        raise ValueError("wait_df is empty")
    return float((wait_df["W"] < 0).mean())


def non_negativity_report(wait_df: pd.DataFrame) -> pd.DataFrame:
    """Per-stop non-negativity violation counts and rates."""
    df = wait_df.copy()
    df["위반"] = df["W"] < 0

    report = (
        df.groupby(["표준버스정류장ID", "정류장명"])
        .agg(총_시간대수=("위반", "size"), 위반_횟수=("위반", "sum"))
        .reset_index()
    )
    report["위반율"] = report["위반_횟수"] / report["총_시간대수"]
    return report.sort_values("표준버스정류장ID").reset_index(drop=True)


def day_end_closure_residual(wait_df: pd.DataFrame, last_hour: int = 23) -> pd.DataFrame:
    """Per-stop |W(s, last_hour)| -- distance from emptying out by day's end."""
    end = wait_df.loc[
        wait_df["시간대"] == last_hour, ["표준버스정류장ID", "정류장명", "W"]
    ].copy()
    if end.empty:
        raise ValueError(f"no rows found for 시간대={last_hour}")

    end = end.rename(columns={"W": "일마감_W"})
    end["잔차"] = end["일마감_W"].abs()
    return end.sort_values("표준버스정류장ID").reset_index(drop=True)


def build_validation_report(wait_df: pd.DataFrame, last_hour: int = 23) -> dict[str, float]:
    """Corridor-wide summary: overall violation rate and mean day-end residual."""
    return {
        "비음수_위반율": non_negativity_violation_rate(wait_df),
        "일마감_평균잔차": float(day_end_closure_residual(wait_df, last_hour)["잔차"].mean()),
    }


def run(wait_path: Path, report_path: Path, last_hour: int = 23) -> None:
    """Read corridor_wait.parquet, compute per-stop reports, write a combined CSV."""
    wait_df = pd.read_parquet(wait_path)

    nn_report = non_negativity_report(wait_df)
    closure_report = day_end_closure_residual(wait_df, last_hour)
    combined = nn_report.merge(
        closure_report[["표준버스정류장ID", "일마감_W", "잔차"]],
        on="표준버스정류장ID",
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(report_path, index=False, encoding="utf-8-sig")

    summary = build_validation_report(wait_df, last_hour)
    print(f"비음수 위반율: {summary['비음수_위반율']:.1%}")
    print(f"일마감 평균 잔차: {summary['일마감_평균잔차']:,.1f}")


if __name__ == "__main__":
    run(
        Path("data/processed/corridor_wait.parquet"),
        Path("data/processed/validation_report.csv"),
    )
