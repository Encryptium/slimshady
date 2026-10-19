"""Checks against the actual downloaded release; skipped before data ingestion."""
import json
import numpy as np
import pytest
import rasterio
from services.geo import DATA,RAW

pytestmark=pytest.mark.skipif(not (DATA/'samples.npz').exists(),reason='Build original source data first')

def test_canopy_samples_match_original_raster():
    with np.load(DATA/'samples.npz') as s, rasterio.open(RAW/'canopy/UTCMosaic2023.tif') as raster:
        indices=np.linspace(0,len(s['xy'])-1,1000,dtype=int)
        actual=np.array([int(v[0]==1) for v in raster.sample(s['xy'][indices])])
        np.testing.assert_array_equal(actual,s['canopy'][indices])
        assert raster.crs.to_epsg()==26916

def test_graph_samples_and_topology_are_consistent():
    graph=json.loads((DATA/'graph.json').read_text());edges=graph['edges']
    with np.load(DATA/'samples.npz') as s:
        assert sum(e['sample_count'] for e in edges)==len(s['xy'])
        for e in edges:
            assert e['length']>0 and e['sample_count']>0
            assert str(e['u']) in graph['nodes'] and str(e['v']) in graph['nodes']
            assert not e['opening_hours']
        assert np.all(np.isfinite(s['xy']))

def test_lidar_heights_require_source_evidence():
    path=DATA/'buildings-height.json'
    if not path.exists():pytest.skip('LiDAR not processed')
    buildings=json.loads(path.read_text())
    for b in buildings:
        if b.get('height_source','') and b['height_source'].startswith('USGS'):
            assert b['lidar_cells']>=6 and b['lidar_acquisition_year']==2018
            assert 2<=b['height']<350
