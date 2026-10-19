"""Human-readable place locations from source tags, with honest street fallbacks."""

def mapped_address(tags):
    street = tags.get('addr:street') or tags.get('addr:place')
    line = tags.get('addr:full') or (' '.join(filter(None, [tags.get('addr:housenumber'), street])) if street else None)
    if not line:
        return None
    city = tags.get('addr:city', 'Atlanta')
    state = tags.get('addr:state', 'GA')
    postcode = tags.get('addr:postcode')
    return ', '.join(filter(None, [line, city, ' '.join(filter(None, [state, postcode]))]))


def enrich_locations(places, raw, edges):
    import json
    from shapely.geometry import Point, LineString
    from shapely import STRtree
    from services.geo import project

    wanted = {p['id'] for p in places}
    addresses = {}
    for path in [*sorted(raw.glob('osm-?-?.json')), raw/'osm-named-areas.json']:
        if not path.exists():
            continue
        for element in json.loads(path.read_text())['elements']:
            key = element['type'][0] + str(element['id'])
            if key in wanted:
                address = mapped_address(element.get('tags', {}))
                if address:
                    addresses[key] = address
    streets = [e for e in edges if e['highway'] in {'residential','unclassified','service','tertiary','secondary','primary','living_street'} and e['name'] not in {'Walking path','Local street','Crosswalk'}]
    lines = [project(LineString(e['coords'])) for e in streets]
    tree = STRtree(lines)
    for place in places:
        address = addresses.get(place['id'])
        if address:
            place['address'] = address
            continue
        if place['id'].startswith('s'):
            place['locationLabel'] = f"{place['name']}, Atlanta, GA"
            continue
        point = project(Point(place['longitude'], place['latitude']))
        nearest = tree.nearest(point) if lines else None
        if nearest is not None and lines[int(nearest)].distance(point) <= 250:
            place['locationLabel'] = f"Near {streets[int(nearest)]['name']} · Atlanta, GA"
        else:
            place['locationLabel'] = 'Atlanta, GA'
    return places
