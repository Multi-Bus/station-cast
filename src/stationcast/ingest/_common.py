"""Helpers shared by multiple ingest/ collectors (issue #104).

oa12913.py, oa12912.py, and route_schedule.py each read a raw CSV keyed by
표준버스정류장ID/역명, and 역명 carries the same trailing per-route sequence
suffix regardless of dataset. Every raw file in this project also happens
to share the same cp949 encoding (기상청/서울시 공개데이터 공통 관례).
"""

import re
from pathlib import Path
from typing import Any

import pandas as pd

_NAME_SUFFIX_RE = re.compile(r"\(\d+\)$")


def clean_stop_name(name: object) -> str:
    """Strip the trailing per-route sequence number from a raw 역명 value."""
    return _NAME_SUFFIX_RE.sub("", str(name))


def read_cp949_csv(csv_path: Path, **kwargs: Any) -> pd.DataFrame:
    """Read a raw cp949-encoded CSV. Extra kwargs pass through to pd.read_csv."""
    return pd.read_csv(csv_path, encoding="cp949", **kwargs)
