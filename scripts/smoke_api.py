"""End-to-end checks using actual local data and the running service."""
import json,time
from pathlib import Path
import httpx

def main():
    c=httpx.Client(base_url='http://127.0.0.1:8765',timeout=240)
    assert c.get('/health/ready').json()['ready']
    a=c.get('/v1/search',params={'q':'Clough'}).json()['results'][0]
    b=c.get('/v1/search',params={'q':'Barnes Georgia Tech'}).json()['results'][0]
    assert c.get('/v1/search',params={'q':'8th Street'}).json()['results']
    body={'origin':a,'destination':b,'departureTime':'2026-09-26T13:00:00-04:00','preferences':{'avoidStairs':True,'maxExtraRatio':.2,'maxExtraSeconds':600}}
    tick=time.monotonic();r=c.post('/v1/routes',json=body);r.raise_for_status();data=r.json()
    fast=next(p for p in data['routes'] if 'fastest' in p['badges'])
    best=next(p for p in data['routes'] if 'recommended' in p['badges'])
    assert best['extraSeconds']<=min(fast['durationSeconds']*.2,600)+1
    assert best['uncoveredSeconds']<=fast['uncoveredSeconds']+.1
    for route in data['routes']:
        assert route['geometry']['coordinates'] and 0<=route['coverFraction']<=1
        assert not any(s['properties']['steps'] for s in route['segments']['features'])
        assert abs(sum(s['properties']['length'] for s in route['segments']['features'])-route['distanceMeters'])<10
    report={'seconds':round(time.monotonic()-tick,2),'origin':a,'destination':b,'routes':[{k:p[k] for k in ['badges','distanceMeters','durationSeconds','coverFraction','uncoveredSeconds','extraSeconds']} for p in data['routes']]}
    print(json.dumps(report,indent=2),flush=True)
    body['departureTime']='2026-09-26T01:00:00-04:00'
    night=c.post('/v1/routes',json=body);night.raise_for_status()
    assert night.json()['night'] and all(p['coverFraction'] is None for p in night.json()['routes'])
    body['origin']={'longitude':-73.9,'latitude':40.7}
    invalid=c.post('/v1/routes',json=body)
    assert invalid.status_code==422 and invalid.json()['detail']['code']=='OUTSIDE_COVERAGE'
    out=Path('artifacts');out.mkdir(exist_ok=True)
    (out/'route-smoke.json').write_text(json.dumps(data,indent=2))
    (out/'api-verification.json').write_text(json.dumps(report,indent=2))
    print('PASS: real search, connected routes, detour budget, no stairs, geometry metrics, night, coverage rejection.')
if __name__=='__main__':main()
