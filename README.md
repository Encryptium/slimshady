# SlimShady

An Atlanta walking app built with Expo / React Native and a local FastAPI geospatial service. Compare the fastest walk with routes that trade a bounded amount of extra walking for less modeled uncovered time.

**New collaborator with no datasets? Follow [SETUP_INSTRUCTIONS.md](SETUP_INSTRUCTIONS.md) from the beginning.** All commands in this README run from the repository's `shade_app/` directory.

**Plan a loop:** Choose **Make a loop**, set your start, pick walk or jog, and choose a duration and shade preference. Results return to the same mapped start, stay within 30% of the requested duration, and avoid excessive retracing. Some starts may have no suitable loop. The search is approximate, and shade estimates use the same model as point-to-point routes.

**Run the built app:** `http://127.0.0.1:8765`. Choose **Try a Georgia Tech route**, then **Find routes**. Search also accepts mapped places and street names; map pins let you choose a specific entrance.

## Run locally

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 22+, and original data downloaded with the scripts below. The current workspace already contains downloaded and processed data. Allow several GB of disk and at least 4 GB free RAM; 8 GB is preferable for ingestion.

```powershell
uv sync --frozen
npm --prefix apps/mobile ci
npm --prefix apps/mobile run build
.venv\Scripts\python.exe scripts/serve.py
```

On macOS/Linux use `.venv/bin/python`. Startup loads the graph and spatial indexes before `/health/ready` becomes available. The single server serves the web app, canopy tiles, search and routing. No map or geocoding API key is needed. Basemap tiles require internet access.

For Expo development, keep the API running and run `npm --prefix apps/mobile start`. Web development uses port 8081 and the API on 8765. To use a physical phone, start the API with `--host 0.0.0.0` and set `EXPO_PUBLIC_API_URL` to a reachable API URL in `apps/mobile/.env.local`. Prefer HTTPS. The default development URL is derived from Expo's LAN host.

## Native app

This uses the native MapLibre module, so **Expo Go is insufficient**. Development, Android preview APK and production profiles are in `apps/mobile/eas.json`.

```powershell
cd apps/mobile
# Set EXPO_PUBLIC_API_URL to the reachable HTTPS API before bundling.
npx eas-cli@latest build --profile development --platform android
# Or an installable internal APK:
npx eas-cli@latest build --profile preview --platform android
```

EAS requires your Expo account/project and signing setup; iOS distribution also requires the relevant Apple credentials. No account or signing credentials are embedded. Bundling and dependency checks can run locally; a physical-device build and outdoor GPS validation are separate checks. Navigation is foreground-only and requests location only when used.

## Original data pipeline

No synthetic geometry, generated trees, guessed building floors, or randomized shade scores enter production. Each download has a source URL, retrieval timestamp, byte count and SHA-256 in `data/manifests/`. Raw and processed data are intentionally excluded from Git.

```powershell
.venv\Scripts\python.exe scripts/acquire_data.py all
.venv\Scripts\python.exe scripts/build_data.py
.venv\Scripts\python.exe scripts/build_search.py
.venv\Scripts\python.exe scripts/acquire_data.py lidar
.venv\Scripts\python.exe scripts/acquire_data.py lidar_tiles
.venv\Scripts\python.exe scripts/build_heights.py
```

Run these in order. Downloads are cached; LiDAR is roughly 857 MB and its public host can be slow. Restart the API after rebuilding data. `build_heights.py` requires the selected 2018 USGS source CRS and classified returns, rather than silently accepting unrelated elevations.

| Source | Actual release | Use |
| --- | --- | --- |
| [Georgia Tech / City of Atlanta canopy](https://geospatial.gatech.edu/AtlantaUTC/) | Original 2023 WorldView-2 classification, approximately 1 m | Sample mapped crown cover every approximately 3 m of walking geometry; render original raster |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | September 26, 2026 snapshot | 129,572 walking segments, access rules, crossings, stairs, 15,510 searchable places/access points |
| [USGS 3DEP](https://www.usgs.gov/3d-elevation-program) | 49 tiles, GA_Statewide_2018_B18_DRRA | Classified local ground and building returns; 16,671 additional building heights |

There are 16,949 available building heights including explicit OSM heights. LiDAR coverage is concentrated around central Atlanta, **not citywide**. Canopy and walking coverage follow the Atlanta municipal study boundary. More details and accuracy limitations are in [DATA_QUALITY.md](DATA_QUALITY.md).

## What works

- Real city walking graph, origin/destination search, map pins and location.
- Fastest / recommended / shade-first candidates; detour cap, pace and avoiding mapped stairs.
- Atlanta-local departure date/time, solar-position building shadows evaluated at arrival times, nighttime handling.
- MapLibre maps on web and native, original canopy overlay, colored route segments and alternatives.
- Saved walks on device, foreground GPS progress, off-route recalculation, optional spoken instructions.
- Source/limitation view, live NWS weather when available, SQLite reports pending review.

The app labels results **modeled cover**. Tree shadow movement, leaf seasonality, missing building heights, terrain and current path obstructions are not established by these datasets. It does not claim measured cooling or guaranteed shade. See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the broader production roadmap; this repository implements the usable local app, not every future research and operational milestone.

## Validation

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts/smoke_api.py
npm --prefix apps/mobile run typecheck
npm --prefix apps/mobile run lint
cd apps/mobile
npx expo-doctor
npm run test:browser
npx expo export --platform ios --platform android --output-dir dist-native
```

The API smoke test needs the running service and original data. Browser smoke needs installed Chrome; it uses a temporary browser session and writes screenshots to `artifacts/`. It exercises real routes, saving, source disclosure and a mobile viewport. Python tests include deliberately small synthetic **test-only** graphs for edge cases, plus direct comparisons against the original canopy raster.

## Hosting

`Dockerfile` builds the web client and Python service. Mount the existing `data` directory at `/app/data`; the image does not redistribute the original datasets. `docker compose up --build` exposes port 8765. Docker is optional and the container recipe must be validated on your deployment host. Put HTTPS and durable report storage in front of any public release. Keep one API worker per process: spatial data and caches consume memory, and this version serializes expensive route calculations. Scale by independent workers/instances behind a queue or gateway after load testing.

Public OSM raster tiles are appropriate for a small interactive prototype; do not bulk download them or promise offline maps. Arrange a production tile provider before large-scale distribution. The canopy publisher offers a download but does not name a redistribution license in the catalog; establish terms before redistributing source raster files.

## Layout

- `apps/mobile/src/app`: Expo Router screen and layout.
- `apps/mobile/src/components`: separate web/native MapLibre renderers.
- `services`: API, path graph, solar geometry and cover scoring.
- `scripts`: original source ingestion, processing and real-data smoke checks.
- `data/manifests`: reproducible source records.
- `tests`: routing invariants, shadow geometry and dataset checks.

Reports store only the submitted position/category/note. Search and route requests are processed locally by this service; no user account or route history database is required. Report submission never silently edits the graph.

## Interface

Calendar departure selection uses Atlanta local time. Desktop directions float alongside the map; smaller screens use a directions sheet. Selecting a step focuses its location. Route tracing and camera transitions respect reduced-motion settings. Search displays source addresses where available, otherwise a nearby-street label. The two glass panels have opaque fallbacks.
