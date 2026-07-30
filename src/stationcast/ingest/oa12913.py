"""OA-12913 boarding/alighting collector and corridor builder.

Builds the Jongno-Myeongdong-Euljiro corridor datasets described in
data/README.md from the raw Seoul Open Data Plaza CSVs (OA-12913 and the
bus stop coordinate dataset).
"""

import re
from pathlib import Path

import pandas as pd

# Jongno-Myeongdong-Euljiro corridor: 21 stops confirmed in data/README.md
CORRIDOR_STOP_IDS: tuple[int, ...] = (
    100000385,
    100000386,
    100000387,
    100000388,
    100000389,
    100000390,
    100000391,
    100000392,
    101000021,
    101000027,
    101000032,
    101000040,
    101000041,
    101000042,
    101000043,
    101000057,
    101000059,
    101000060,
    101000061,
    101000114,
    101000141,
)

_NAME_SUFFIX_RE = re.compile(r"\(\d+\)$")
_HOUR_RE = re.compile(r"(\d+)시")


def _clean_stop_name(name: object) -> str:
    """Strip the trailing per-route sequence number from a raw 역명 value."""
    return _NAME_SUFFIX_RE.sub("", str(name))


def load_boarding_alighting(csv_path: Path) -> pd.DataFrame:
    """Load the raw OA-12913 monthly CSV (cp949-encoded)."""
    return pd.read_csv(csv_path, encoding="cp949", low_memory=False)


def load_stop_coordinates(csv_path: Path) -> pd.DataFrame:
    """Load the Seoul bus stop coordinate CSV (cp949-encoded)."""
    return pd.read_csv(csv_path, encoding="cp949", low_memory=False)


def build_corridor_hourly(
    boarding_df: pd.DataFrame, stop_ids: tuple[int, ...] = CORRIDOR_STOP_IDS
) -> pd.DataFrame:
    """Aggregate route-level rows into stop x hour boarding/alighting totals.

    Sums across every route serving a stop, since the queue balance model
    is stop-independent (see data/README.md section 3).
    """
    sub = boarding_df[boarding_df["표준버스정류장ID"].isin(stop_ids)].copy()
    sub["정류장명"] = sub["역명"].apply(_clean_stop_name)

    on_cols = [c for c in boarding_df.columns if c.endswith("시승차총승객수")]
    off_cols = [c for c in boarding_df.columns if c.endswith("시하차총승객수")]

    frames = []
    for on_col, off_col in zip(on_cols, off_cols, strict=True):
        match = _HOUR_RE.match(on_col)
        assert match is not None, f"unexpected hour column name: {on_col}"
        hour = int(match.group(1))
        grp = (
            sub.groupby(["표준버스정류장ID", "정류장명"])
            .agg(승차=(on_col, "sum"), 하차=(off_col, "sum"))
            .reset_index()
        )
        grp["시간대"] = hour
        frames.append(grp)

    result = pd.concat(frames, ignore_index=True)
    return (
        result[["표준버스정류장ID", "정류장명", "시간대", "승차", "하차"]]
        .sort_values(["표준버스정류장ID", "시간대"])
        .reset_index(drop=True)
    )


def build_corridor_stops(
    boarding_df: pd.DataFrame,
    coord_df: pd.DataFrame,
    stop_ids: tuple[int, ...] = CORRIDOR_STOP_IDS,
) -> pd.DataFrame:
    """Build per-stop metadata (name, ARS number, coordinates) for the corridor."""
    sub = boarding_df[boarding_df["표준버스정류장ID"].isin(stop_ids)].copy()
    sub["정류장명"] = sub["역명"].apply(_clean_stop_name)
    meta = sub[["표준버스정류장ID", "정류장명", "버스정류장ARS번호"]].drop_duplicates(
        subset="표준버스정류장ID"
    )
    meta = meta.rename(columns={"버스정류장ARS번호": "ARS번호"})

    coords = coord_df[["정류소번호", "X좌표", "Y좌표", "정류소 타입"]].drop_duplicates(
        subset="정류소번호"
    )
    result = meta.merge(coords, left_on="표준버스정류장ID", right_on="정류소번호", how="left")
    return (
        result.drop(columns=["정류소번호"])
        .sort_values("표준버스정류장ID")
        .reset_index(drop=True)
    )


def run(raw_dir: Path, out_dir: Path) -> None:
    """Build corridor_hourly.parquet and corridor_stops.parquet from raw_dir CSVs."""
    boarding_csv = next(raw_dir.glob("*버스노선별_정류장별_시간대별_승하차*.csv"))
    coord_csv = next(raw_dir.glob("*버스정류소*위치정보*.csv"))

    boarding_df = load_boarding_alighting(boarding_csv)
    coord_df = load_stop_coordinates(coord_csv)

    hourly = build_corridor_hourly(boarding_df)
    stops = build_corridor_stops(boarding_df, coord_df)

    out_dir.mkdir(parents=True, exist_ok=True)
    hourly.to_parquet(out_dir / "corridor_hourly.parquet", index=False)
    stops.to_parquet(out_dir / "corridor_stops.parquet", index=False)


if __name__ == "__main__":
    run(Path("data/raw"), Path("data/processed"))
