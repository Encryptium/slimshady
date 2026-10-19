# Evidence and accuracy

The app is an evidence-based prototype, not a field-validated sunlight instrument.

## Tree canopy

The source is Georgia Tech's original `UTCMosaic2023.tif`, downloaded from `https://cura.design.gatech.edu/UTC/UTCMosaic2023.zip`. The classified raster is NAD83 / UTM 16N (EPSG:26916), approximately 1 m resolution. Class 1 is mapped canopy. Zero is absence from the clipped canopy mask; interpretation is restricted to the original municipal study area. The build samples this raster directly, rather than extracting color from a screenshot or inferring trees from generic land-use polygons.

Mapped crown coverage is binary. It is not a measured transmittance, leaf-density or temperature model. Shadows cast to the side of trees, trunk clearance and seasonal leaf loss are not modeled. Data age can overstate cover where trees have been removed. Leaf-off dates carry an explicit warning.

## Buildings

Footprints and explicit heights come from OSM. The current source graph contains building ways; multipart building relations are not comprehensively reconstructed, so some large buildings are absent. Unknown heights remain unknown.

49 original USGS LiDAR tiles cover the selected central district (`[-84.42, 33.745, -84.365, 33.805]`; tile extents extend beyond this selection rectangle). Horizontal coordinates are EPSG:6350, with NAVD88 / Geoid12B elevations in metres. The processor uses only class 2 ground and class 6 building returns, rasterized at 2 m. Ground gaps are filled only within 30 m of an actual ground return. Buildings require at least six accepted roof cells. Height is the 90th percentile of roof-minus-local-ground; explicit OSM heights take precedence. Full method and counts are written to `data/processed/height-quality.json`.

The 2018 acquisition can disagree with current footprints. Roof classification, nearby terrain, ground interpolation, mixed roof heights and footprint alignment all contribute uncertainty. These derived heights have not been checked against surveyed building heights.

Building shadows extrude a footprint to its available height and sweep it opposite the solar azimuth onto a locally flat plane at a 1 m receiver height. Sun position uses pvlib and central Atlanta coordinates. Five-minute time buckets are applied at segment arrival midpoints. Terrain relief, facade detail, overhangs and cloud cover are not modeled. Metrics are withheld below 5 degrees solar elevation; nighttime routes report no direct sunlight rather than inventing a shade percentage.

## Walking geometry

OSM node topology is preserved; visual line intersections do not automatically create a crossing. Motorways, explicit prohibited/private access, driveways, indoor paths and unsupported conditional opening hours are excluded. Arterial road centerlines require sidewalk tags. Where sidewalks are separately mapped, the road is not duplicated as a pedestrian shortcut. Pedestrian one-way restrictions and avoiding stairs are applied.

67,444 of 129,572 graph segments are explicitly mapped pedestrian geometry. Remaining eligible street-centerline geometry does not establish exact sidewalk position. Route responses disclose the proportion using that approximation. The network has 3,155 connected components; disconnected points return a clear error rather than drawing a straight line or fabricating a link. Origin/destination snapping is limited to 80 m. Pin-to-path approaches are not counted as verified walking guidance.

Search uses actual OSM names, relation centers, building representative points and mapped street points. A place center is not necessarily an entrance. Long streets can have multiple access results. Arbitrary house-number interpolation and external address geocoding are not implemented; choose the entrance on the map when necessary.

## Routing interpretation

The fastest path minimizes estimated walking duration, including stairs and a fixed crossing delay. Multiple candidate searches penalize uncovered segments by different amounts. Candidates are rescored at their expected traversal times; the app chooses the lowest uncovered duration within the user's detour budget. This is an approximate candidate search, not a proof of a globally optimal time-dependent route. The displayed percentage is distance-weighted modeled cover, while uncovered minutes include estimated traversal delays.

Shadow calculations are limited to a conservative spatial envelope that contains routes meeting the candidate time budget. Buildings outside the envelope are still included when their projected shadow bounds intersect it. This reduces runtime without inventing heights or dropping relevant shadow casters solely because their footprint is outside the walk area.

## Before claims of production accuracy

Perform field measurements across seasons and times; audit connectivity and crossings; reconstruct missing building relations; expand/re-date height coverage; model canopy heights and crown transmission; benchmark detour optimality and GPS behavior; and verify wheelchair routes separately. Background navigation, offline map packs, live closures, turn-angle navigation and citywide LiDAR coverage are not yet implemented. Foreground instructions identify mapped paths and crossings; they are not a substitute for checking road conditions.
