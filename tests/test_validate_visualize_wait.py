"""Tests for per-stop wait-population curve visualization (issue #17)."""

from pathlib import Path

import pandas as pd
import pytest

from stationcast.validate.visualize_wait import save_overview_grid

# These tests don't set a Korean-capable font (run() does, via sns.set_theme,
# for the real committed image) -- matplotlib's default DejaVu Sans has no
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


def test_save_overview_grid_writes_one_file(tmp_path: Path) -> None:
    out_path = tmp_path / "overview.png"
    result = save_overview_grid(_wait_df(), out_path)

    assert result == out_path
    assert out_path.exists()


def test_save_overview_grid_rejects_wrong_stop_count(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="expected 21"):
        save_overview_grid(_wait_df(n_stops=3), tmp_path / "overview.png")
