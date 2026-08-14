"""Tests for the field-survey-derived per-stop capacity table (issue #12)."""

from stationcast.ingest.oa12913 import CORRIDOR_STOP_IDS
from stationcast.ingest.stop_capacity import (
    CAPACITY_PER_PLATFORM,
    PLATFORM_COUNTS,
    build_stop_capacity,
)


def test_platform_counts_cover_every_corridor_stop_exactly_once() -> None:
    assert set(PLATFORM_COUNTS.keys()) == set(CORRIDOR_STOP_IDS)
    assert len(PLATFORM_COUNTS) == len(CORRIDOR_STOP_IDS)


def test_build_stop_capacity_derives_capacity_from_platform_count() -> None:
    result = build_stop_capacity()
    capacity_by_stop = result.set_index("표준버스정류장ID")["포용인원"]

    # 롯데백화점: 2 승차대 -> 20명
    assert capacity_by_stop[101000041] == 2 * CAPACITY_PER_PLATFORM
    # 종로4가.종묘: 3 승차대 -> 30명
    assert capacity_by_stop[100000392] == 3 * CAPACITY_PER_PLATFORM
    # 염천교: 1 승차대 -> 10명
    assert capacity_by_stop[101000021] == 1 * CAPACITY_PER_PLATFORM


def test_build_stop_capacity_has_one_row_per_stop() -> None:
    result = build_stop_capacity()
    assert len(result) == len(CORRIDOR_STOP_IDS)
    assert result["표준버스정류장ID"].is_unique
