"""Loop invariants checked against the downloaded pedestrian network."""
from pathlib import Path
import pytest
from pydantic import ValidationError
from services.api import LoopRequest
from services.routing import Router, RouteError
from services.loops import loop_routes
from services.geo import DATA

@pytest.fixture(scope='module')
def router():
    if not (DATA/'graph.json').exists():
        pytest.skip('Original local data required')
    return Router()

def request(**changes):
    return {'origin':{'longitude':-84.3963748,'latitude':33.7746658},'departureTime':'2026-09-27T13:00:00-04:00',
            'durationMinutes':30,'activity':'walk','shadePreference':'more_shade','avoidStairs':True,**changes}

@pytest.mark.parametrize('activity',['walk','jog'])
def test_closed_loops_respect_duration_access_and_retracing(router,activity):
    result=loop_routes(router,request(activity=activity))
    assert 1<=len(result['routes'])<=3
    for route in result['routes']:
        coords=route['geometry']['coordinates']
        assert coords[0]==coords[-1]
        assert len(set(tuple(p) for p in coords))>3
        assert 1260<=route['durationSeconds']<=2340
        assert route['retracedFraction']<=.25
        assert 0<=route['coverFraction']<=1
        assert not any(f['properties']['steps'] for f in route['segments']['features'])
        assert abs(sum(f['properties']['seconds'] for f in route['segments']['features'])-route['durationSeconds'])<10
        assert route['instructions'][-1]['text']=='Return to your starting point'

def test_night_does_not_claim_shade(router):
    result=loop_routes(router,request(departureTime='2026-09-27T01:00:00-04:00'))
    assert result['night']
    assert all(r['coverFraction'] is None and r['uncoveredSeconds']==0 for r in result['routes'])

def test_loop_validates_request_and_coverage(router):
    with pytest.raises(ValidationError):LoopRequest(**request(durationMinutes=500))
    with pytest.raises(ValidationError):LoopRequest(**request(departureTime='2026-09-27T13:00:00'))
    with pytest.raises(RouteError,match='coverage'):
        loop_routes(router,request(origin={'longitude':-73.9,'latitude':40.7}))
