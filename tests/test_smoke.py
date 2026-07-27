"""Placeholder test to confirm the CI pipeline runs end-to-end."""

import stationcast


def test_package_importable() -> None:
    assert stationcast is not None
