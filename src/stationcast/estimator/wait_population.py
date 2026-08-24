"""Per-route wait-population estimator (대기인원 추정).

Replaces the queue-balance reservoir model (formerly estimator/
queue_balance.py + features/calibration.py + estimator/scipy_calibration.py).

This estimator applies Little's Law (L = lambda * W) per route,
using only real per-route boarding (OA-12913) and real per-route headway
(route_schedule.py's corridor_route_schedule.parquet) -- no calibrated or
optimized free parameters:

    W(s,t) = sum_r B_r(s,t) * (headway_r / 2) * (1 + cv_r**2) / 60

B_r(s,t) is route r's boarding at stop s in hour t (people/hour); dividing
by 60 turns it into people/minute, the arrival rate Little's Law expects.
headway_r/2 is the textbook average wait for a passenger arriving at a
random time relative to a perfectly regular schedule (the inspection/
waiting-time paradox's zero-variance case). (1 + cv_r**2) corrects for
irregular (bunched) headways: a schedule whose inter-arrival times have
coefficient of variation cv_r has expected wait (headway/2)(1+cv_r**2), not
just headway/2.

cv_r is derived per route from corridor_route_schedule.parquet's 최소배차/
최대배차 (that route's registered headway range, 서울시버스노선기본정보) --
no separate calibration or real-time polling needed. Assuming headway is
uniformly distributed over [최소배차, 최대배차], its std is
(최대배차-최소배차)/sqrt(12), so cv_r = std / 배차간격. Routes missing
최소배차/최대배차 fall back to the median of the stop's other routes that
hour, same fallback as 배차간격.
"""

from pathlib import Path

import pandas as pd

from stationcast.ingest.route_schedule import fill_missing_headway

DEFAULT_DAY_TYPE = "평일"


def estimate_wait(
    route_hourly: pd.DataFrame,
    route_schedule: pd.DataFrame,
    day_type: str = DEFAULT_DAY_TYPE,
) -> pd.DataFrame:
    """Compute W(s,t) for every stop and hour from per-route boarding and headway.

    route_hourly: 표준버스정류장ID, 정류장명, 노선번호, 시간대, 승차
        (see ingest/oa12913.py's build_corridor_route_hourly).
    route_schedule: 표준버스정류장ID, 노선번호, 요일유형, 배차간격, 최소배차,
        최대배차, 배차정보없음 (see ingest/route_schedule.py's
        build_corridor_route_schedule), filtered here to ``day_type`` (평일
        by default -- the corridor's weekday routes have full headway
        coverage; see data/README.md).

    Routes with no schedule row, or flagged 배차정보없음, fall back to the
    median headway/registered-range of the *other* routes serving the same
    stop that hour via ingest.route_schedule.fill_missing_headway (shared
    with validate/physical_constraints.py's capacity check) -- a single
    missing route shouldn't zero out or drop that route's real boarding
    count. A stop with no schedule data on any of its routes raises
    ValueError instead of silently producing a NaN W.

    Returns 표준버스정류장ID, 정류장명, 시간대, W -- one row per (stop, hour),
    summed across every route serving that stop.
    """
    schedule = route_schedule[route_schedule["요일유형"] == day_type]
    schedule = schedule[~schedule["배차정보없음"]][
        ["표준버스정류장ID", "노선번호", "배차간격", "최소배차", "최대배차"]
    ]

    merged = route_hourly.merge(schedule, on=["표준버스정류장ID", "노선번호"], how="left")
    merged = fill_missing_headway(merged, ["배차간격", "최소배차", "최대배차"])

    cv = ((merged["최대배차"] - merged["최소배차"]) / (12**0.5)) / merged["배차간격"]
    merged["평균대기_분"] = (merged["배차간격"] / 2) * (1 + cv**2)
    merged["W_r"] = merged["승차"] * merged["평균대기_분"] / 60

    result = (
        merged.groupby(["표준버스정류장ID", "정류장명", "시간대"])
        .agg(W=("W_r", "sum"))
        .reset_index()
    )
    return result.sort_values(["표준버스정류장ID", "시간대"]).reset_index(drop=True)


def run(
    route_hourly_path: Path,
    route_schedule_path: Path,
    out_path: Path,
    day_type: str = DEFAULT_DAY_TYPE,
) -> None:
    """Read corridor_route_hourly/corridor_route_schedule, compute W(s,t), write it."""
    route_hourly = pd.read_parquet(route_hourly_path)
    route_schedule = pd.read_parquet(route_schedule_path)
    result = estimate_wait(route_hourly, route_schedule, day_type=day_type)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(out_path, index=False)


if __name__ == "__main__":
    run(
        Path("data/processed/corridor_route_hourly.parquet"),
        Path("data/processed/corridor_route_schedule.parquet"),
        Path("data/processed/corridor_wait.parquet"),
    )
