from services.search import mapped_address

def test_explicit_address():
    assert mapped_address({'addr:housenumber':'266','addr:street':'4th Street NW','addr:postcode':'30332'}) == '266 4th Street NW, Atlanta, GA 30332'

def test_missing_address_never_invents_number():
    assert mapped_address({'name':'Campus library','amenity':'library'}) is None
    assert mapped_address({'addr:street':'Spring Street NW'}) == 'Spring Street NW, Atlanta, GA'

    assert mapped_address({'addr:housenumber':'266'}) is None


def test_location_fallback_is_nearby_street_not_fabricated_address(tmp_path):
    from services.search import enrich_locations
    places = [{'id':'n1','name':'Test destination','longitude':-84.39,'latitude':33.77},
              {'id':'n2','name':'Distant destination','longitude':-84.5,'latitude':33.8}]
    edges = [{'highway':'residential','name':'Fourth Street Northwest','coords':[[-84.391,33.77],[-84.389,33.77]]}]
    enrich_locations(places, tmp_path, edges)
    assert places[0]['locationLabel'] == 'Near Fourth Street Northwest · Atlanta, GA'
    assert 'address' not in places[0]
    assert places[1]['locationLabel'] == 'Atlanta, GA'
