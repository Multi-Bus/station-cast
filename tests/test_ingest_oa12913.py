"""Tests for the OA-12913 corridor builder."""

import pandas as pd
import pytest

from stationcast.ingest.oa12913 import build_corridor_route_hourly, build_corridor_stops


def _boarding_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "표준버스정류장ID": [100000389, 100000389, 100000389, 999999999],
            "노선번호": ["150", "271", "N15", "150"],
            "역명": ["종로2가(00063)", "종로2가(00073)", "종로2가(00099)", "다른정류장(00001)"],
            "버스정류장ARS번호": ["01014", "01014", "01014", "09999"],
            "사용년월": [202606, 202606, 202606, 202606],  # June 2026 -> 30 days
            # values are x30 of the old fixture so that, after the
            # daily-average normalization, the expected sums are unchanged.
            "0시승차총승객수": [300, 150, 60, 90],
            "0시하차총승객수": [30, 60, 60, 120],
            "1시승차총승객수": [210, 90, 30, 30],
            "1시하차총승객수": [0, 30, 30, 60],
        }
    )


def _coord_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "정류소번호": [100000389],
            "X좌표": [126.986535],
            "Y좌표": [37.570238],
            "정류소 타입": ["중앙차로"],
        }
    )


def test_build_corridor_route_hourly_normalizes_by_days_in_month() -> None:
    # 202602 = Feb 2026 (not a leap year -> 28 days). Values only divide
    # evenly by 28, not 30, to catch any code that hardcodes 30.
    df = pd.DataFrame(
        {
            "표준버스정류장ID": [100000389],
            "노선번호": ["150"],
            "역명": ["종로2가(00063)"],
            "버스정류장ARS번호": ["01014"],
            "사용년월": [202602],
            "0시승차총승객수": [280],
        }
    )

    result = build_corridor_route_hourly(df, stop_ids=(100000389,))

    assert result.iloc[0]["승차"] == 10.0  # 280 / 28


def test_build_corridor_route_hourly_keeps_routes_separate_and_flags_night_buses() -> None:
    result = build_corridor_route_hourly(_boarding_df(), stop_ids=(100000389,))

    assert list(result["표준버스정류장ID"].unique()) == [100000389]
    assert set(result["정류장명"]) == {"종로2가"}
    # 3 routes (150, 271, N15) x 2 hours = 6 rows, not summed together.
    assert len(result) == 6
    assert set(result["노선번호"]) == {"150", "271", "N15"}

    hour0_150 = result[(result["시간대"] == 0) & (result["노선번호"] == "150")].iloc[0]
    assert hour0_150["승차"] == 10  # 300 / 30, not summed with 271's 150
    assert bool(hour0_150["is_night_bus"]) is False

    hour0_271 = result[(result["시간대"] == 0) & (result["노선번호"] == "271")].iloc[0]
    assert hour0_271["승차"] == 5  # 150 / 30
    assert bool(hour0_271["is_night_bus"]) is False

    hour0_n15 = result[(result["시간대"] == 0) & (result["노선번호"] == "N15")].iloc[0]
    assert hour0_n15["승차"] == 2  # 60 / 30
    assert bool(hour0_n15["is_night_bus"]) is True


def test_build_corridor_route_hourly_weights_multi_month_average_by_day_count() -> None:
    # Feb 2026 (28 days, 10/day alone) and June 2026 (30 days, 20/day alone)
    # for the same stop/route/hour, concatenated the way run() does across
    # every monthly CSV. The two months have deliberately different per-day
    # rates so the correct combined average -- (month totals summed) /
    # (day counts summed) = 880 / 58 -- can't be produced by a bug that
    # drops one month, swaps in the wrong day count, or averages the two
    # months' own daily rates instead of their raw totals.
    feb = pd.DataFrame(
        {
            "표준버스정류장ID": [100000389],
            "노선번호": ["150"],
            "역명": ["종로2가(00063)"],
            "버스정류장ARS번호": ["01014"],
            "사용년월": [202602],
            "0시승차총승객수": [280],  # 280 / 28 = 10/day alone
        }
    )
    june = pd.DataFrame(
        {
            "표준버스정류장ID": [100000389],
            "노선번호": ["150"],
            "역명": ["종로2가(00063)"],
            "버스정류장ARS번호": ["01014"],
            "사용년월": [202606],
            "0시승차총승객수": [600],  # 600 / 30 = 20/day alone
        }
    )
    combined = pd.concat([feb, june], ignore_index=True)

    result = build_corridor_route_hourly(combined, stop_ids=(100000389,))

    assert len(result) == 1  # one (stop, route, hour) row, months merged
    assert result.iloc[0]["승차"] == pytest.approx(880 / 58)  # (280 + 600) / (28 + 30)


def test_build_corridor_route_hourly_keeps_one_series_when_stop_name_changes() -> None:
    # ID 101000042 was renamed 해운센터.롯데영플라자 -> 소공동.롯데영플라자
    # mid-window in the real 12-month data; grouping by name as well as ID
    # would silently split one physical stop's hour-0 boarding into two rows.
    old_name_month = pd.DataFrame(
        {
            "표준버스정류장ID": [101000042],
            "노선번호": ["150"],
            "역명": ["해운센터.롯데영플라자(00001)"],
            "버스정류장ARS번호": ["02001"],
            "사용년월": [202503],
            "0시승차총승객수": [300],
        }
    )
    new_name_month = pd.DataFrame(
        {
            "표준버스정류장ID": [101000042],
            "노선번호": ["150"],
            "역명": ["소공동.롯데영플라자(00001)"],
            "버스정류장ARS번호": ["02001"],
            "사용년월": [202606],
            "0시승차총승객수": [300],
        }
    )
    combined = pd.concat([old_name_month, new_name_month], ignore_index=True)

    result = build_corridor_route_hourly(combined, stop_ids=(101000042,))

    assert len(result) == 1  # one (stop, route, hour) row, not split by name
    assert result.iloc[0]["정류장명"] == "소공동.롯데영플라자"  # most recent name wins
    assert result.iloc[0]["승차"] == pytest.approx((300 + 300) / (31 + 30))


def test_build_corridor_stops_merges_name_ars_and_coordinates() -> None:
    result = build_corridor_stops(_boarding_df(), _coord_df(), stop_ids=(100000389,))

    assert len(result) == 1
    row = result.iloc[0]
    assert row["표준버스정류장ID"] == 100000389
    assert row["정류장명"] == "종로2가"
    assert row["ARS번호"] == "01014"
    assert row["X좌표"] == 126.986535
    assert row["정류소 타입"] == "중앙차로"
