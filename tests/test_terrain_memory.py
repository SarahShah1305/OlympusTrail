"""Memory optimizations preserve source precision and keep health probes cheap."""
import numpy as np
from fastapi.testclient import TestClient
from olympustrail.api import create_app, ROOT
from olympustrail.terrain import TerrainGrid, RasterLayers

def test_health_reads_manifest_without_loading_rasters(monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError('health must not load terrain')
    monkeypatch.setattr(TerrainGrid,'load',forbidden)
    monkeypatch.delenv('OLYMPUSTRAIL_DATASET',raising=False)
    app=create_app()
    body=TestClient(app).get('/health').json()
    assert body['status']=='ok'
    assert body['grid_shape']==[2134,1244]
    assert body['grid_spacing_m']==500
    assert app.state.grid is None

def test_lazy_float32_sources_and_aliases():
    grid=TerrainGrid.load(ROOT)
    assert isinstance(grid.layers,RasterLayers)
    assert grid.layers.cache=={}
    source=grid.layers['temperature_lt12']
    assert source.dtype==np.float32
    assert grid.layers['scenario_temperature'] is source
    assert 'pressure' not in grid.layers.cache
    assert 'aspect' not in grid.layers.cache

def test_chunked_projection_matches_cell_coordinates():
    grid=TerrainGrid.load(ROOT)
    lon,lat=grid.lonlat
    for cell in [(0,0),(643,1226),(2133,1243)]:
        position=grid.position(cell)
        assert np.rad2deg(lon[cell]) == position['lon']
        assert np.rad2deg(lat[cell]) == position['lat']
