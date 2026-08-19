"""Per-stop wait-population curve visualization (issue #17).

Renders W(s,t) -- Little's Law's per-hour waiting-population estimate from
estimator/wait_population.py -- as a single overview grid (all 21 corridor
stops as small multiples) so every stop's curve can be checked at a glance
in one image. Report/presentation material only; no computation happens
here.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless-safe (CI has no display); must precede pyplot import

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

EXPECTED_STOP_COUNT = 21


def save_overview_grid(wait_df: pd.DataFrame, out_path: Path) -> Path:
    """Save all 21 stops' W(t) curves as small multiples in one grid image.

    wait_df: 표준버스정류장ID, 정류장명, 시간대, W (estimator/wait_population.py's
        output, e.g. corridor_wait.parquet).

    Raises if wait_df doesn't cover exactly the expected 21 corridor stops,
    since issue #17's definition of done requires confirming all 21 exist.
    """
    stop_ids = sorted(wait_df["표준버스정류장ID"].drop_duplicates().tolist())
    if len(stop_ids) != EXPECTED_STOP_COUNT:
        raise ValueError(
            f"expected {EXPECTED_STOP_COUNT} stops in wait_df, found {len(stop_ids)}"
        )

    n_cols = 3
    n_rows = -(-len(stop_ids) // n_cols)  # ceil division
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(6 * n_cols, 3.6 * n_rows))
    axes_flat = axes.flatten()

    for ax, stop_id in zip(axes_flat, stop_ids, strict=False):
        stop_df = wait_df[wait_df["표준버스정류장ID"] == stop_id].sort_values("시간대")
        name = str(stop_df["정류장명"].iloc[0])
        sns.lineplot(data=stop_df, x="시간대", y="W", marker="o", markersize=4, ax=ax)
        ax.set_title(f"{name} ({stop_id})", fontsize=11)
        ax.set_xlabel("시간대(시)", fontsize=9)
        ax.set_ylabel("대기인원(명)", fontsize=9)
        ax.set_xlim(0, 23)
        ax.set_xticks(range(0, 24, 3))
        ax.tick_params(axis="both", labelsize=9, labelbottom=True, labelleft=True)
        ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True, nbins=6))
        ax.set_ylim(bottom=0)

    for ax in axes_flat[len(stop_ids) :]:
        ax.set_visible(False)

    fig.suptitle("정류장별 대기인원 W(s,t) — 21개 전체", fontsize=16, y=0.995)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.97))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def run(wait_path: Path, out_path: Path) -> None:
    wait_df = pd.read_parquet(wait_path)
    sns.set_theme(style="whitegrid", font="Malgun Gothic")

    saved_path = save_overview_grid(wait_df, out_path)
    print(f"전체 개요 차트 저장: {saved_path}")


if __name__ == "__main__":
    run(Path("data/processed/corridor_wait.parquet"), Path("docs/wait_curves/overview.png"))
