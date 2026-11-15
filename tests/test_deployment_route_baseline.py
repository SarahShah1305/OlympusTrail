"""Golden real-terrain responses recorded before lazy loading and float32 storage."""
import json
from pathlib import Path
import pytest
from olympustrail.api import ROOT
from olympustrail.models import RouteRequest
from olympustrail.terrain import TerrainGrid
from olympustrail.routing import plan_route
CASES=json.loads((Path(__file__).parent/'fixtures/deployment_route_baseline.json').read_text())
@pytest.fixture(scope='module')
def terrain(): return TerrainGrid.load(ROOT)
@pytest.mark.parametrize('case',CASES,ids=lambda case:case['name'])
def test_deployment_route_is_identical_to_baseline(terrain,case):
    assert plan_route(terrain,RouteRequest(**case['request'])) == case['expected']
