"""Small synthetic graphs are test fixtures only; production uses source datasets."""
import math
import networkx as nx
import numpy as np
import pytest
from shapely.geometry import LineString, Point, box
from services.routing import Router
from services.shade import swept_shadow, ShadeModel
from scripts.build_data import eligible

@pytest.mark.parametrize('tags',[
    {'highway':'motorway'}, {'highway':'footway','foot':'no'},
    {'highway':'footway','access':'private'}, {'highway':'service','service':'driveway'},
    {'highway':'primary'}, {'highway':'residential','sidewalk':'separate'},
    {'highway':'cycleway'}, {'highway':'footway','indoor':'yes'},
])
def test_restricted_ways_excluded(tags):
    assert not eligible(tags)

@pytest.mark.parametrize('tags',[
    {'highway':'footway'}, {'highway':'residential'},
    {'highway':'primary','sidewalk':'both'}, {'highway':'cycleway','foot':'yes'},
])
def test_eligible_walkways(tags):
    assert eligible(tags)

def tiny_router(oneway='no'):
    r=Router.__new__(Router)
    r.edges=[{'id':0,'u':10,'v':11,'length':100.,'steps':False,'crossing':False,'foot_oneway':oneway,'sample_count':4,'sample_start':0}]
    r.lines=[LineString([(0,0),(100,0)])];r.graph=nx.MultiDiGraph()
    if oneway!='-1':r.graph.add_edge(10,11,key=0,eid=0,length=100.,reverse=False)
    if oneway not in {'yes','1','true'}:r.graph.add_edge(11,10,key=0,eid=0,length=100.,reverse=True)
    return r

def test_same_edge_snaps_preserve_partial_length():
    r=tiny_router();g=r.query_graph({'eid':0,'offset':20},{'eid':0,'offset':75},False)
    assert nx.shortest_path_length(g,-1,-2,weight='length')==pytest.approx(55)
    assert nx.shortest_path_length(g,-2,-1,weight='length')==pytest.approx(55)

@pytest.mark.parametrize('oneway,forward',[('yes',True),('-1',False)])
def test_pedestrian_oneway_after_splitting(oneway,forward):
    r=tiny_router(oneway);g=r.query_graph({'eid':0,'offset':20},{'eid':0,'offset':75},False)
    assert nx.has_path(g,-1,-2)==forward
    assert nx.has_path(g,-2,-1)!=forward

def test_partial_edge_samples_not_full_edge_average():
    r=tiny_router();profile={'sample_cover':np.array([0,0,1,1],dtype=bool)}
    assert r.fraction({'eid':0,'start':.5,'stop':1},profile)==1
    assert r.fraction({'eid':0,'start':0,'stop':.5},profile)==0

def test_shadow_sweep_direction_and_area():
    shadow=swept_shadow(box(0,0,10,10),0,-20)
    assert shadow.bounds==(0,-20,10,10)
    assert shadow.area==pytest.approx(300)
    assert not shadow.covers(Point(5,15))

def test_solar_position_separates_noon_and_night():
    from datetime import datetime
    noon=datetime.fromisoformat('2026-06-21T13:30:00-04:00').timestamp()
    midnight=datetime.fromisoformat('2026-06-21T00:30:00-04:00').timestamp()
    assert ShadeModel.sun(noon)[1]>70
    assert ShadeModel.sun(midnight)[1]<0
