import httpx
import pytest
from scripts import acquire_data

def test_osm_post_rejection_falls_back_to_get(monkeypatch):
    methods=[]
    def handler(request):
        methods.append(request.method)
        return httpx.Response(406 if request.method=='POST' else 200,json={'elements':[]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(acquire_data,'C',client)
        data,url=acquire_data.fetch_osm('[out:json];node(1);out;')
    assert data=={'elements':[]} and methods==['POST','GET']
    assert url=='https://overpass-api.de/api/interpreter'

def test_osm_rejects_partial_error_response(monkeypatch):
    def handler(request):
        return httpx.Response(200,json={'elements':[],'remark':'runtime error: timed out'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(acquire_data,'C',client)
        with pytest.raises(RuntimeError,match='Both Overpass endpoints failed'):
            acquire_data.fetch_osm('[out:json];node(1);out;')
