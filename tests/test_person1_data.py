from pathlib import Path

import numpy as np
import pytest

from olympustrail.terrain import TerrainGrid
from scripts.prepare_person1_layers import interpolate, parse_export

ROOT = Path(__file__).resolve().parents[1]


def test_bilinear_interpolation_preserves_known_plane_and_rejects_extrapolation():
    lons, lats = np.array([0., 2.]), np.array([0., 4.])
    values = np.array([[0., 2.], [8., 10.]])  # z = lon + 2*lat
    actual = interpolate(lons, lats, values, np.array([[1.]]), np.array([[1.]]))
    assert actual[0, 0] == pytest.approx(3)
    with pytest.raises(ValueError, match="beyond"):
        interpolate(lons, lats, values, np.array([[3.]]), np.array([[1.]]))


def test_source_coordinate_axes_and_physical_variables_are_consistent():
    source = ROOT / "data/person1/sources"
    lons, lats, tables = parse_export(source/"mcd62_ls90_noon.txt", source/"mcd62_longitude_axis.txt")
    assert (len(lons), len(lats)) == (64, 48)
    assert lons[0] == 186 and lons[-1] == 204
    assert lats[0] == 39 and lats[-1] == 53
    temperature, dust, sunlight, pressure = tables
    assert 100 < temperature.min() < temperature.max() < 400
    assert 0 <= dust.min() < dust.max() < 10
    assert sunlight.min() >= 0 and pressure.min() > 0


def test_observed_temperature_is_separate_from_complete_model_scenario():
    terrain = TerrainGrid.load(ROOT)
    measured = terrain.layers["observed_temperature"]
    assert np.isfinite(measured).sum() == 2972
    assert np.isnan(measured).sum() == 49388
    assert np.isfinite(terrain.layers["scenario_temperature"]).all()
    assert terrain.metadata["supplemental"]["regional_measurements_complete"] is False
    assert terrain.metadata["supplemental"]["scenario_layers_ready"] is True
    radiation = terrain.layers["radiation"]
    assert np.ptp(radiation) == 0  # No invented spatial shielding signal.
