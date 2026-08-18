"""Physical constraint checking — non-negativity and capacity (issue #5).

Quantifies how well an estimator's W(s,t) output satisfies the physical
constraints scoped to this module:

- Non-negativity: W(s,t) >= 0 (a waiting population can't be negative).
  Under estimator/wait_population.py this holds by construction (W is a
  sum of non-negative boarding times non-negative wait), so this check is
  now a data-integrity guard rather than something expected to fail.
- Capacity: the wait-population model's entire justification is that this
  corridor has no carryover -- a bus never arrives too full for everyone
  waiting to board. That is an assumption about the real world, not
  something the model can prove about itself, so it has to be checked
  against real boarding and headway data instead.

Day-end closure (W(s, last_hour) ~= 0) was the previous queue-balance
model's constraint, checking that a reservoir of carried-over demand
emptied out by day's end. wait_population.py has no reservoir -- W(s,t) is
computed independently each hour -- so day-end closure is trivially true
regardless of whether the model is right, and has been replaced here with
the capacity check, which is the constraint that actually exercises the
model's core assumption.
"""

from pathlib import Path

import pandas as pd

BUS_CAPACITY = 46.0
"""Assumed 정원 (seated + standing) for every route in the corridor, since
no per-route vehicle-capacity data exists yet -- parallel to
ingest/stop_capacity.py's 10-per-platform assumption. This is a placeholder
pending a real per-route source; override via the ``bus_capacity`` parameter
if one becomes available."""

DEFAULT_DAY_TYPE = "평일"


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


def capacity_violation_report(
    route_hourly: pd.DataFrame,
    route_schedule: pd.DataFrame,
    day_type: str = DEFAULT_DAY_TYPE,
    bus_capacity: float = BUS_CAPACITY,
) -> pd.DataFrame:
    """Per (stop, route, hour) capacity utilization, assuming every bus arrives empty.

    route_hourly: 표준버스정류장ID, 정류장명, 노선번호, 시간대, 승차
        (see ingest/oa12913.py's build_corridor_route_hourly).
    route_schedule: 표준버스정류장ID, 노선번호, 요일유형, 배차간격, 배차정보없음
        (see ingest/route_schedule.py's build_corridor_route_schedule).

    수송능력_r(s,t) = (60 / 배차간격_r) * bus_capacity is the most generous
    possible capacity for that hour -- 0% 재차율, i.e. every arriving bus
    already empty. 위반 = 실측 승차 B_r(s,t) > 수송능력_r(s,t): even under
    that most generous assumption, more people boarded than could possibly
    fit. This is the only way to detect real carryover without knowing
    demand directly -- if boarding never reaches capacity, no one could
    have been left behind, because there was room to spare.

    Missing headway (no schedule row, or flagged 배차정보없음) falls back
    to the median headway of the stop's other routes that hour, same as
    estimator/wait_population.py.
    """
    schedule = route_schedule[route_schedule["요일유형"] == day_type]
    schedule = schedule[~schedule["배차정보없음"]][["표준버스정류장ID", "노선번호", "배차간격"]]

    merged = route_hourly.merge(schedule, on=["표준버스정류장ID", "노선번호"], how="left")
    merged["배차간격"] = merged["배차간격"].fillna(
        merged.groupby("표준버스정류장ID")["배차간격"].transform("median")
    )

    merged["수송능력"] = (60 / merged["배차간격"]) * bus_capacity
    merged["이월"] = (merged["승차"] - merged["수송능력"]).clip(lower=0.0)
    merged["위반"] = merged["이월"] > 0

    cols = [
        "표준버스정류장ID",
        "정류장명",
        "노선번호",
        "시간대",
        "승차",
        "수송능력",
        "이월",
        "위반",
    ]
    return (
        merged[cols]
        .sort_values(["표준버스정류장ID", "노선번호", "시간대"])
        .reset_index(drop=True)
    )


def capacity_violation_rate(
    route_hourly: pd.DataFrame,
    route_schedule: pd.DataFrame,
    day_type: str = DEFAULT_DAY_TYPE,
    bus_capacity: float = BUS_CAPACITY,
) -> float:
    """Fraction of (stop, route, hour) rows where boarding exceeds capacity."""
    report = capacity_violation_report(route_hourly, route_schedule, day_type, bus_capacity)
    if len(report) == 0:
        raise ValueError("route_hourly is empty")
    return float(report["위반"].mean())


def build_validation_report(
    wait_df: pd.DataFrame,
    route_hourly: pd.DataFrame,
    route_schedule: pd.DataFrame,
    day_type: str = DEFAULT_DAY_TYPE,
    bus_capacity: float = BUS_CAPACITY,
) -> dict[str, float]:
    """Corridor-wide summary: non-negativity rate and capacity violation rate."""
    capacity_rate = capacity_violation_rate(route_hourly, route_schedule, day_type, bus_capacity)
    return {
        "비음수_위반율": non_negativity_violation_rate(wait_df),
        "용량_위반율": capacity_rate,
    }


def run(
    wait_path: Path,
    route_hourly_path: Path,
    route_schedule_path: Path,
    report_path: Path,
    day_type: str = DEFAULT_DAY_TYPE,
    bus_capacity: float = BUS_CAPACITY,
) -> None:
    """Read corridor_wait/corridor_route_hourly/corridor_route_schedule, write a combined report."""
    wait_df = pd.read_parquet(wait_path)
    route_hourly = pd.read_parquet(route_hourly_path)
    route_schedule = pd.read_parquet(route_schedule_path)

    nn_report = non_negativity_report(wait_df)
    capacity_report = capacity_violation_report(
        route_hourly, route_schedule, day_type, bus_capacity
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    nn_report.to_csv(report_path, index=False, encoding="utf-8-sig")
    capacity_report.to_csv(
        report_path.with_name(report_path.stem + "_capacity" + report_path.suffix),
        index=False,
        encoding="utf-8-sig",
    )

    summary = build_validation_report(wait_df, route_hourly, route_schedule, day_type, bus_capacity)
    print(f"비음수 위반율: {summary['비음수_위반율']:.1%}")
    print(f"용량 위반율: {summary['용량_위반율']:.1%}")


if __name__ == "__main__":
    run(
        Path("data/processed/corridor_wait.parquet"),
        Path("data/processed/corridor_route_hourly.parquet"),
        Path("data/processed/corridor_route_schedule.parquet"),
        Path("data/processed/validation_report.csv"),
    )
