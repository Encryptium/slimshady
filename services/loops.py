"""Bounded loop candidates on the real pedestrian graph; no straight-line connectors."""
import math
import time
from datetime import datetime
import networkx as nx
from services.geo import project
from shapely.geometry import Point
from services.routing import RouteError


def repeated_ratio(graph, path):
    """Fraction of distance retraced, counting both directions of the same edge."""
    seen = set()
    repeated = total = 0.
    for u, v in zip(path, path[1:]):
        edge = graph[u][v]
        total += edge['length']
        key = (edge['eid'], round(edge['start'], 7), round(edge['stop'], 7))
        if key in seen:
            repeated += edge['length']
        seen.add(key)
    return repeated / max(total, 1.)


def loop_routes(router, request):
    tick = time.monotonic()
    departure = datetime.fromisoformat(request['departureTime'].replace('Z', '+00:00')).timestamp()
    target = request['durationMinutes'] * 60
    speed = 2.6 if request['activity'] == 'jog' else 1.3
    avoid = request.get('avoidStairs', False)
    start = router.snap(request['origin'], avoid)
    graph = router.query_graph(start, start, avoid)
    # Both snaps are identical. Merge the temporary endpoints into a single root.
    nx.contracted_nodes(graph, -1, -2, self_loops=False, copy=False)
    duration = lambda u, v, a: router.duration(a, speed)
    distances, paths = nx.single_source_dijkstra(graph, -1, cutoff=target*.65, weight=duration)
    graph = graph.subgraph(distances).copy()
    router.shade.set_region(start['point'], start['point'], speed*target*1.3)
    profile = router.shade.at(departure)
    night = profile['elevation'] <= 0
    low_sun = 0 < profile['elevation'] <= 5
    # Select nearby graph nodes in each direction and at two useful distances.
    nodes = []
    for node, seconds in distances.items():
        if node < 0 or seconds < target*.2:
            continue
        point = project(Point(router.nodes[node]))
        angle = math.atan2(point.y-start['point'].y, point.x-start['point'].x)
        nodes.append((node, seconds, angle))
    anchors = set()
    for k in range(12):
        angle = 2*math.pi*k/12-math.pi
        sector = [(node, seconds) for node, seconds, a in nodes if abs(math.atan2(math.sin(a-angle), math.cos(a-angle))) <= math.pi/6]
        for ratio in (.32, .45):
            if sector:
                anchors.add(min(sector, key=lambda p: abs(p[1]-target*ratio))[0])
    raw = []
    signatures = set()
    for anchor in sorted(anchors):
        outward = paths[anchor]
        used = {graph[u][v]['eid'] for u, v in zip(outward, outward[1:])}
        for shade_weight in (0., 2.):
            def return_cost(u, v, edge):
                uncovered = 0 if night or low_sun else 1-profile['fraction'][edge['eid']]
                return duration(u, v, edge) * (1 + shade_weight*uncovered + (8 if edge['eid'] in used else 0))
            try:
                home = nx.shortest_path(graph, anchor, -1, weight=return_cost)
            except nx.NetworkXNoPath:
                continue
            path = outward + home[1:]
            seconds = sum(duration(u, v, graph[u][v]) for u, v in zip(path, path[1:]))
            if not target*.7 <= seconds <= target*1.3 or len(set(path)) < 4:
                continue
            retraced = repeated_ratio(graph, path)
            if retraced > .25:
                continue
            signature = frozenset(graph[u][v]['eid'] for u, v in zip(path, path[1:]))
            if signature in signatures:
                continue
            signatures.add(signature)
            exposure = sum(duration(u, v, graph[u][v])*(1-profile['fraction'][graph[u][v]['eid']]) for u, v in zip(path, path[1:]))/seconds
            preference = {'balanced':.25, 'more_shade':.8, 'most_shade':1.5}[request['shadePreference']]
            time_weight = {'balanced':1., 'more_shade':.6, 'most_shade':.15}[request['shadePreference']]
            score = time_weight*abs(seconds-target)/target + retraced*.3 + (0 if night or low_sun else exposure*preference)
            raw.append((score, path, signature, retraced))
    if not raw:
        raise RouteError('NO_LOOP_FOUND', 'No suitable loop was found here at this duration. Try a longer time or a nearby starting point.')
    raw.sort(key=lambda candidate:candidate[0])
    # Arrival-time scoring is expensive; shortlist before evaluating exact cover.
    evaluated = []
    for _, path, signature, retraced in raw[:8]:
        result = router.evaluate(graph, path, departure, speed)
        if result['distanceMeters'] < 1:
            continue
        preference = {'balanced':.25, 'more_shade':.8, 'most_shade':1.5}[request['shadePreference']]
        time_weight = {'balanced':1., 'more_shade':.6, 'most_shade':.15}[request['shadePreference']]
        score = time_weight*abs(result['durationSeconds']-target)/target + retraced*.3
        if not night and not low_sun:
            score += preference * result['uncoveredSeconds']/result['durationSeconds']
        evaluated.append((score, result, signature, retraced))
    evaluated.sort(key=lambda item:item[0])
    selected = []
    selected_signatures = []
    for _, route, signature, retraced in evaluated:
        if any(len(signature & other)/max(1,len(signature | other)) > .8 for other in selected_signatures):
            continue
        number = len(selected)+1
        route.update(id=f'loop-{number}', kind='loop', badges=['recommended'] if number==1 else [],
                     label='Best match' if number==1 else f'Loop {number}', extraSeconds=0, savedUncoveredSeconds=None,
                     retracedFraction=round(retraced,3), targetDurationSeconds=target)
        route['instructions'][-1]['text'] = 'Return to your starting point'
        if night:
            route.update(uncoveredSeconds=0, coverFraction=None)
        elif low_sun:
            route.update(uncoveredSeconds=None, coverFraction=None)
        selected.append(route)
        selected_signatures.append(signature)
        if len(selected)==3:
            break
    if not selected:
        raise RouteError('NO_LOOP_FOUND', 'No suitable loop was found. Try another start or duration.')
    warnings = ['Loop durations are approximate; options stay within 30% of your requested time.',
                'Some loops retrace a short section near the starting point.',
                'Tree cover uses the 2023 crown map. Missing building heights and seasonal leaf loss are not modeled.',
                'Follow actual sidewalks and crossings. Path access has not been field-verified.']
    if night:
        warnings.append('No direct sunlight is expected. Shade preferences are ignored after dark.')
    if low_sun:
        warnings.append('The sun is too low for a reliable shade estimate. Shade metrics are withheld.')
    return {'routes':selected, 'mode':'loop', 'activity':request['activity'], 'targetDurationSeconds':target,
            'departureTime':request['departureTime'], 'timeZone':'America/New_York', 'release':router.release,
            'model':'2023 mapped crown cover + geometric building shadows', 'approximateSearch':True,
            'candidateCount':len(raw), 'night':night, 'lowSun':low_sun, 'sunElevation':round(profile['elevation'],1),
            'warnings':warnings, 'snapped':{key:{'coordinate':start['coords'],'distanceMeters':round(start['distance'],1)} for key in ('origin','destination')},
            'processingMs':round((time.monotonic()-tick)*1000)}
