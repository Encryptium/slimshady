# ShadeATL: setup from a clean clone (no datasets included)

These instructions rebuild the real Atlanta datasets, build the Expo web client, and start the app. **You do not need the original developer's computer, local files, or API keys.** Internet access and the public data hosts are required. Native phone builds are covered separately below.

The Git repository contains source code, dependency lockfiles and small source-provenance manifests. It deliberately excludes `data/raw`, `data/processed`, the reports database, `.venv`, `node_modules`, Expo caches, screenshots and compiled app bundles. Do not expect the app to start immediately after cloning: run the data pipeline first.

## 1. Install prerequisites

- Git.
- **Node.js 22.17 or newer within Node 22 LTS**, with npm. The original build used Node 22.17.0. Install from [Node.js](https://nodejs.org/en/download).
- **uv**, the Python environment/package manager. Follow its [installation instructions](https://docs.astral.sh/uv/getting-started/installation/). The project was locked with uv 0.7.2; use that version or a newer compatible uv release.
- Python **3.12**. You can install it yourself, or let the `uv sync --python 3.12` command below provision it.
- For the optional browser test, install desktop **Google Chrome**. Chrome is not required to run the app in your normal browser.

Use a 64-bit machine. Reserve **at least 10 GB free disk** and preferably **8 GB available RAM** for dependency installation, raw data and processing. LiDAR alone is approximately 857 MB across 49 files; other downloads, the extracted raster, Node dependencies and generated graph add to that. This is a conservative working-space allowance, not the repository download size.

The first setup can take an hour or more on slow public data servers. The original LiDAR download took roughly 45 minutes. Leave download commands running unless they print an error. Subsequent starts use local files and do not download again.

## 2. Clone and enter the app directory

```sh
git clone https://github.com/ThePyProgrammer/hackgt-2026.git
cd hackgt-2026/shade_app
```

If you received a ZIP or already cloned the repository, open a terminal in its **`shade_app`** directory instead. Every command below runs there unless a step explicitly changes directories. Do not run the data scripts from the repository's parent directory.

Verify the tools:

```sh
node --version
npm --version
uv --version
```

## 3. Install locked dependencies

```sh
uv sync --frozen --python 3.12
npm --prefix apps/mobile ci
```

`uv` creates `shade_app/.venv`. `npm ci` creates `apps/mobile/node_modules` from the lockfile. Do not copy another person's virtual environment or `node_modules`; both are machine/platform dependent. There is no required `.env` file for the local browser app.

On Windows PowerShell, if `npm` is blocked by an execution-policy error, use **`npm.cmd`** in place of `npm` in these commands. No PowerShell policy change is necessary.

## 4. Download the real source data

Run each command separately. **Wait for it to exit successfully before continuing.** The commands are the same on Windows, macOS and Linux because `uv run` selects the correct Python executable.

```sh
uv run --frozen python scripts/acquire_data.py canopy
uv run --frozen python scripts/acquire_data.py boundary
uv run --frozen python scripts/acquire_data.py osm
```

This downloads:

| Command | Public source | Files / purpose |
| --- | --- | --- |
| `canopy` | Georgia Tech / City of Atlanta | Original 2023 approximately 1 m canopy ZIP, extracted to `data/raw/canopy/UTCMosaic2023.tif` |
| `boundary` | Georgia Tech / Atlanta ArcGIS service | Municipal study boundary in `data/raw/boundary.geojson` |
| `osm` | Public OpenStreetMap Overpass endpoints | Four actual OSM extracts: `osm-0-0.json`, `osm-0-1.json`, `osm-1-0.json`, `osm-1-1.json` |

These sources are public and require no API key. The scripts record source URLs, download timestamps and checksums in `data/manifests`. **OSM is a live source:** your download may contain newer edits and produce different graph counts/routes from the original September 26, 2026 build. Included manifests describe that original build; a new download updates its corresponding manifests. They are not a bundled historical OSM snapshot.

If a public endpoint times out, returns 429, 502, 503 or 504, wait several minutes and rerun the failed command. The OSM downloader tries alternative request methods/endpoints. Completed OSM quadrants and downloaded raster/LiDAR files are reused. Incomplete binary downloads use `.part` files and restart that file on the next run; they do not resume byte ranges. Do not run several ingestion processes simultaneously. If every endpoint remains unavailable, the download is blocked externally; there is no fake-data fallback.

## 5. Build the walking graph, then place search

```sh
uv run --frozen python scripts/build_data.py
uv run --frozen python scripts/build_search.py
```

`build_data.py` reads the four OSM extracts and original canopy raster, preserves OSM topology, applies access rules and writes the graph, sample arrays, building footprints and quality metadata.

`build_search.py` downloads an additional small OSM named-area extract and builds the local place/street search index. **Do not skip it:** it adds relation-based landmarks such as Clough, used in the example walk.

At this point these files should exist in `data/processed/`:

```text
boundary.geojson
graph.json
samples.npz
buildings.json
places.json
quality.json
search.json
```

## 6. Download and process LiDAR building heights

Complete this step to reproduce the enhanced building-shadow model:

```sh
uv run --frozen python scripts/acquire_data.py lidar
uv run --frozen python scripts/acquire_data.py lidar_tiles
uv run --frozen python scripts/build_heights.py
```

The first command queries the USGS catalog and creates `data/raw/lidar-catalog.json`. The second selects and downloads the 2018 central-Atlanta tiles into `data/raw/lidar/`. The third derives heights from classified building and ground returns and creates:

```text
data/processed/buildings-height.json
data/processed/height-quality.json
```

The original release processed 49 tiles and had 16,949 available building heights including explicit OSM heights. Those are reference counts, not assertions about a future live-source rebuild.

If USGS is temporarily unavailable, you can run the app after step 5, but it will use **only the available OSM building heights**. That is a reduced model, not equivalent to the full setup. Finish this step and restart the API to load the LiDAR heights. Do not run `build_heights.py` against a partial tile download and assume the result has full coverage.

LiDAR coverage is concentrated around central Atlanta, not the whole city. Canopy is from 2023; LiDAR is from 2018. There are no generated tree locations or guessed building-floor heights. See [DATA_QUALITY.md](DATA_QUALITY.md) for the actual accuracy limitations.

## 7. Build and start the browser app

```sh
npm --prefix apps/mobile run build
uv run --frozen python scripts/serve.py
```

Leave the second command running. Wait for **`Application startup complete`** and the Uvicorn listening message; loading the graph can take a minute. Open:

- App: **http://127.0.0.1:8765/**
- Readiness: **http://127.0.0.1:8765/health/ready**
- API documentation: **http://127.0.0.1:8765/docs**

Select **Try a Georgia Tech walk**, then **Find my shaded walk**. The first route computes and caches building shadows, so it may take tens of seconds depending on hardware. The walking graph and canopy are local; the street basemap and live weather still require internet access. NWS failure does not disable route planning.

The web build includes MapLibre's separate worker files automatically through the `prebuild` npm script. Use **`npm run build`**, not a bare `expo export --platform web`, for the initial web build. Missing workers can otherwise produce map tiles without rendered route lines.

Stop the server with **Ctrl+C**. For later sessions, only run:

```sh
cd shade_app
uv run --frozen python scripts/serve.py
```

That `cd` assumes you are at the repository root. No download or frontend rebuild is needed unless code or data changed.

## 8. Verify the installation

Keep the server running and open a second terminal in `shade_app`:

```sh
uv run --frozen python -m pytest -q
uv run --frozen python scripts/smoke_api.py
node apps/mobile/scripts/test-logic.cjs
npm --prefix apps/mobile run typecheck
npm --prefix apps/mobile run lint
npm --prefix apps/mobile run test:browser
```

The browser test requires desktop Google Chrome. It creates an isolated headless session, uses simulated GPS, exercises real API routes, and saves screenshots under `artifacts/`; it does not use your personal browser profile. Python data tests skip when source data has not been built, so passing tests with skips alone does not prove setup is complete. The API smoke test must also succeed.

From `shade_app/apps/mobile`, optional Expo checks are:

```sh
npx expo-doctor
npx expo export --platform ios --platform android --output-dir dist-native
```

Use `npx.cmd` on Windows if PowerShell blocks `npx`. Return to `shade_app` with `cd ../..` afterwards. JavaScript bundle export does **not** create an installable APK/IPA or prove physical-device GPS behavior. See [VERIFICATION.md](VERIFICATION.md) for what was and was not tested originally.

## 9. Develop the client

Keep the API running on 8765. In another terminal at `shade_app`:

```sh
npm --prefix apps/mobile run web
```

Expo serves the development web client on 8081 by default. It connects to the API on 8765, and the backend allows those default local development origins. If Expo offers another port because 8081 is occupied, free the port or configure `EXPO_PUBLIC_API_URL` and `CORS_ORIGINS` explicitly; do not assume another port has the same defaults.

Backend changes require restarting `scripts/serve.py`. Frontend changes appear through Metro in development; rebuild with `npm run build` to update the copy served by the Python server.

## 10. Run on a physical phone / build native

**Expo Go will not work:** this app uses MapLibre's native module. You need an Expo development build or preview build.

1. Run the API on a host reachable by the phone. For a trusted local LAN, use `uv run --frozen python scripts/serve.py --host 0.0.0.0` from `shade_app`. The phone and computer must share the network, and the computer firewall must allow your chosen private-network connection on port 8765. `127.0.0.1` on a phone refers to the phone, not your computer.
2. Copy `apps/mobile/.env.example` to `apps/mobile/.env.local`. Set `EXPO_PUBLIC_API_URL` to the reachable API origin, such as `https://your-api-host.example`, without a trailing `/v1`. Use a real reachable host, not the example value. Prefer HTTPS; Android/iOS cleartext restrictions can block arbitrary HTTP LAN addresses.
3. From `shade_app/apps/mobile`, sign in to your own Expo account and build:

```sh
npx eas-cli@latest login
npx eas-cli@latest build --profile development --platform android
```

EAS can prompt to create/link your Expo project and configure signing; use your own account/project. No EAS project credentials or Apple credentials are included in Git. For iOS, substitute `--platform ios` and supply the appropriate Apple provisioning/device setup.

4. Install the generated development build on your device. From `apps/mobile`, start Metro with `npm start` and open that development session in the installed client.
5. For an internally distributed Android APK with a bundled client, use `npx eas-cli@latest build --profile preview --platform android`. Configure the reachable API URL in that EAS build environment first. **`.env.local` is ignored by Git and is not a reliable way to provide variables to remote EAS builds.** Set `EXPO_PUBLIC_API_URL` in the Expo/EAS environment used by the build, or an explicitly configured `env` entry for that build profile. API URLs are public configuration, not secrets.

Location permissions are requested when used. Navigation is foreground-only. Background navigation, offline maps and physical accuracy are not certified by a successful build. Native distribution is an additional step; the local browser app requires no Expo account.

## 11. Optional Docker deployment

Run the data pipeline **before** starting the container. Docker does not download datasets for you.

From `shade_app`:

```sh
docker compose up --build
```

The image builds the web client and Python dependencies. Compose mounts `./data` at `/app/data`, including the writable reports database, and exposes 8765. Preserve that directory across container replacement. Use HTTPS and deployment-appropriate controls before exposing a public service. This Docker recipe has not yet been verified on a deployment host; it is not needed for local setup.

## Troubleshooting and sharing

| Symptom | What to check |
| --- | --- |
| `Missing built inputs` | Finish data steps 4–6 and web build step 7. Do not create empty placeholder files. |
| Server exits loading `places.json`, `quality.json`, etc. | A processing command did not finish. Rerun `build_data.py`, then `build_search.py`, then `build_heights.py` if using LiDAR. |
| `lidar-catalog.json` missing | Run `acquire_data.py lidar` before `lidar_tiles`. |
| `Address already in use` on 8765 | Stop the old ShadeATL server, or use `scripts/serve.py --port 8766` and browse that port. The built web app uses its own origin; Metro/native clients need their API URL updated. |
| Blank tiles / weather unavailable | Check network access to OSM tiles and `api.weather.gov`; routing itself uses downloaded data. |
| Map background appears but route lines do not | Re-run `npm --prefix apps/mobile run build`; verify `/maplibre/maplibre-gl-worker.mjs` is served. |
| Landmark search missing / example fails | Complete `build_search.py`, restart the server, and inspect the actual search results. Live OSM names can change. You can choose public paths on the map instead. |
| `NO_CONNECTED_ROUTE` | OSM does not connect those snapped points in the eligible network. Choose another public entrance; the app deliberately does not invent a connecting path. |
| Out-of-memory during processing | Close other large apps and use more RAM. The pipeline loads the city graph and raster into memory. |
| New data not reflected in app | Restart the backend to reload indexes and shadow caches. A rebuild of graph/footprints should be followed by search and height rebuilds. |
| `uv --frozen` or `npm ci` lock mismatch | Restore the checked-in matching manifest and lockfile pair; do not delete lockfiles to hide the problem. |

For a **deliberate source refresh**, stop the API and archive the relevant raw files outside `data/raw` first; otherwise cached downloads are reused. Rebuild graph → search → heights together. A fresh OSM download will not necessarily reproduce historical counts or exact routes.

To share code, push the committed Git repository or use `git archive`; do not ZIP your entire working directory. Local ignored directories may contain gigabytes of datasets and dependencies. Small `data/manifests/*.json` files are source records, not the datasets themselves, and can be shared with the code. Your own source downloads can update them; review those differences before committing.

Keep `.env.local`, signing keys, downloaded rasters/point clouds, local reports and generated bundles out of Git. The canopy publisher offers a public download but does not name a redistribution license in the catalog; have collaborators download the source rather than bundling the raw raster into the repository.
