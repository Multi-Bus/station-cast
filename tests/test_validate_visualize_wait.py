"""Tests for per-stop wait-population curve visualization (issue #17)."""

from pathlib import Path

import pandas as pd
import pytest

from stationcast.validate.visualize_wait import (
    EXPECTED_STOP_COUNT,
    plot_stop_wait,
    save_all_stop_plots,
    save_overview_grid,
)

# These tests don't set a Korean-capable font (run() does, via sns.set_theme,
# for the real committed images) -- matplotlib's default DejaVu Sans has no
# Hangul glyphs, so it warns once per Korean character rendered. Cosmetic
# only; harmless in this headless test path.
pytestmark = pytest.mark.filterwarnings("ignore:Glyph.*missing from font")


def _wait_df(n_stops: int = 21) -> pd.DataFrame:
    frames = []
    for i in range(n_stops):
        stop_id = 100000000 + i
        frames.append(
            pd.DataFrame(
                {
                    "표준버스정류장ID": stop_id,
                    "정류장명": f"정류장{i}",
                    "시간대": range(24),
                    "W": [float(h) for h in range(24)],
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def test_plot_stop_wait_returns_figure_for_known_stop() -> None:
    fig = plot_stop_wait(_wait_df(), 100000000)
    assert fig is not None
    assert len(fig.axes) == 1


def test_plot_stop_wait_raises_for_unknown_stop() -> None:
    with pytest.raises(ValueError, match="not found"):
        plot_stop_wait(_wait_df(), 999999999)


def test_save_all_stop_plots_writes_one_png_per_stop(tmp_path: Path) -> None:
    paths = save_all_stop_plots(_wait_df(), tmp_path)

    assert len(paths) == EXPECTED_STOP_COUNT
    assert all(p.exists() for p in paths)
    assert all(p.suffix == ".png" for p in paths)


def test_save_all_stop_plots_rejects_wrong_stop_count(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="expected 21"):
        save_all_stop_plots(_wait_df(n_stops=5), tmp_path)


def test_save_overview_grid_writes_one_file(tmp_path: Path) -> None:
    out_path = tmp_path / "overview.png"
    result = save_overview_grid(_wait_df(), out_path)

    assert result == out_path
    assert out_path.exists()


def test_save_overview_grid_rejects_wrong_stop_count(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="expected 21"):
        save_overview_grid(_wait_df(n_stops=3), tmp_path / "overview.png")
