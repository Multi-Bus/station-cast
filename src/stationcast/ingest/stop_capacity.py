"""Per-stop physical capacity (포용인원) from the team's field survey (issue #12).

포용인원 isn't available from open data, so the team split the corridor's
21 stops three ways and counted each stop's 승차대(platform structure) in
person. Per the team's decision, each platform holds up to 10 people at
full capacity, so 포용인원 = 10 * 승차대개수 -- this is the definition that
estimator/congestion.py's 0.5/1.0 grading ratio assumes.
"""

from pathlib import Path

import pandas as pd

CAPACITY_PER_PLATFORM = 10

PLATFORM_COUNTS: dict[int, int] = {
    101000021: 1,  # 염천교
    100000392: 3,  # 종로4가.종묘
    101000042: 1,  # 소공동.롯데영플라자
    101000059: 1,  # 을지로2가.기업은행본점.서울노동청
    100000385: 3,  # 광화문역
    101000114: 1,  # 남대문시장앞.이회영활동터
    101000041: 2,  # 롯데백화점
    101000040: 1,  # 우리은행종로지점
    100000389: 3,  # 종로2가 (서쪽 승강장)
    101000060: 1,  # 을지로2가.파인에비뉴
    101000141: 1,  # 을지로입구역.광교
    100000390: 3,  # 종로3가.탑골공원 (서쪽 승강장)
    100000388: 3,  # 종로2가 (동쪽 승강장)
    101000043: 1,  # 명동.롯데영프라자
    100000391: 3,  # 종로3가.탑골공원 (동쪽 승강장)
    101000061: 1,  # 을지로3가
    101000027: 1,  # 숭례문
    101000032: 1,  # 북창동.남대문시장
    100000387: 3,  # 종로1가 (동쪽 승강장)
    100000386: 3,  # 종로1가 (서쪽 승강장)
    101000057: 2,  # 을지로입구.로얄호텔
}


def build_stop_capacity() -> pd.DataFrame:
    """Derive 포용인원 = CAPACITY_PER_PLATFORM * 승차대개수 for every corridor stop."""
    return pd.DataFrame(
        {
            "표준버스정류장ID": list(PLATFORM_COUNTS.keys()),
            "포용인원": [
                float(count * CAPACITY_PER_PLATFORM) for count in PLATFORM_COUNTS.values()
            ],
        }
    )


def run(out_dir: Path) -> None:
    """Build stop_capacity.parquet from the field survey's 승차대 counts."""
    capacity = build_stop_capacity()

    out_dir.mkdir(parents=True, exist_ok=True)
    capacity.to_parquet(out_dir / "stop_capacity.parquet", index=False)


if __name__ == "__main__":
    run(Path("data/processed"))
