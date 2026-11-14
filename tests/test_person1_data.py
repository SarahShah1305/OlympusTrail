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


def test_regional_3km_dataset_still_loads_unchanged():
    terrain = TerrainGrid.load(ROOT, dataset="regional_3km")
    measured = terrain.layers["observed_temperature"]
    assert np.isfinite(measured).sum() == 2972
    assert np.isnan(measured).sum() == 49388
    assert np.isfinite(terrain.layers["scenario_temperature"]).all()
    assert terrain.metadata["supplemental"]["regional_measurements_complete"] is False
    assert terrain.metadata["supplemental"]["scenario_layers_ready"] is True
    radiation = terrain.layers["radiation"]
    assert np.ptp(radiation) == 0  # No invented spatial shielding signal.


def test_hires_grid_matches_person2_terrain_and_extends_north():
    terrain = TerrainGrid.load(ROOT)
    assert terrain.pixel_m == 500
    assert terrain.shape == (2134, 1244)
    lats = [terrain.position((r, 600))["lat"] for r in (0, terrain.shape[0] - 1)]
    assert lats[0] == pytest.approx(58, abs=0.01) and lats[1] == pytest.approx(40, abs=0.01)
    measured = terrain.layers["observed_temperature"]
    assert 0.0379 < np.isfinite(measured).mean() < 1  # additional historical observations; no model fill
    for lt in (0, 6, 12, 18):
        assert np.isfinite(terrain.layers[f"temperature_lt{lt:02d}"]).all()
    assert terrain.layers["temperature_lt06"].max() < terrain.layers["temperature_lt12"].min()


def test_radiation_reference_does_not_assume_pressure_or_terrain_attenuation():
    terrain = TerrainGrid.load(ROOT)
    rad = terrain.layers["radiation"]
    assert np.ptp(rad) == 0
    assert rad[0,0] == pytest.approx(0.67/24)
    assert terrain.has_shielding is False
    source = terrain.metadata["manifest"]["sources"]["radiation"]
    assert source["shielding_correction_applied"] is False
    assert source["pressure_correction_applied"] is False
    assert source["absorbed_dose_conversion_applied"] is False
