# Road Trip 2026 — Alps motorcycle route planner

A single-page web app for planning scenic motorcycle road trips through the
French, Swiss, and Italian Alps. Plan loops, get 5 diverse alternatives per
leg, see day splits at ~350 km, export to GPX / KML for use in Google Earth
or your GPS.

## Live URL

Once deployed via GitHub Pages: `https://<your-username>.github.io/<repo-name>/`

## What's bundled offline

- `alps_tiles/` — 220 tiles (0.5° × 0.5°) covering the entire Alps with
  ~4.9 M filtered OSM ways (roads + rideable tracks). ~570 MB gzipped.
- `alps_fuel.json` — 21,300 gas stations across the bbox.
- `alps_spots.json` — cols, lakes, viewpoints, etc.

The app prefers these local files over Overpass live queries, so most
routing requests run entirely offline once the page is loaded.

## Live external services

- **Valhalla** (`valhalla1.openstreetmap.de`) — fallback routing + elevation.
  Public instance, occasional 429/CORS — the app handles gracefully.
- **Overpass API** — fallback for road tiles outside the bundled bbox + POI
  queries that aren't pre-bundled.
- **Photon** (`photon.komoot.io`) + **Nominatim** — geocoding for the search
  bar.
- Tile providers (OpenTopoMap, OpenStreetMap, Esri imagery).

## Refreshing the bundled data

If you want to update the offline tiles to match latest OSM data:

```bash
python3 download_alps.py        # ~1 hour, ~570 MB output
python3 download_alps_fuel.py   # ~5 min, ~2 MB output
```

Both scripts are resumable (skip existing files).

## Local development

```bash
python3 -m http.server 8080
open http://localhost:8080
```

## License / attribution

Map data © OpenStreetMap contributors (ODbL).
Routing engine: Valhalla.
Geocoding: Photon (komoot) + Nominatim.
Tile rendering: Leaflet + OpenTopoMap / Esri / OSM tile providers.
