#!/usr/bin/env python3
"""
Download French + Swiss + Italian Alps road/track network from Overpass in tiles.
Filters to rideable ways only (same rules as the web app's rideability() function).
Saves each tile as gzipped JSON in alps_tiles/.

Resumable: skips tiles that already exist.
Runs for ~1.5-4 hours depending on Overpass load. Rate-limited to be a good citizen.
"""
import os, sys, json, gzip, time, math, urllib.request, urllib.error

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alps_tiles')
os.makedirs(OUT_DIR, exist_ok=True)

# Alps bbox (generous — includes French, Swiss, Italian, + a bit of Austrian/Slovenian)
BBOX_S, BBOX_W, BBOX_N, BBOX_E = 43.0, 5.0, 48.0, 16.0
TILE_SIZE = 0.5  # degrees; ~55 x 40 km at 45° lat

# Same access filters as fetchRoadNetwork() in index.html
ACCESS_FILTER = '["access"!="private"]["access"!="no"]["access"!="customers"]["access"!="forestry"]["access"!="permit"]["access"!="military"]["access"!="destination"]'
MOTOR_FILTER = '["motor_vehicle"!="no"]["motor_vehicle"!="private"]["motor_vehicle"!="forestry"]'
MOTO_FILTER = '["motorcycle"!="no"]["motorcycle"!="private"]'
SAC_FILTER = ('["sac_scale"!="mountain_hiking"]["sac_scale"!="demanding_mountain_hiking"]'
              '["sac_scale"!="alpine_hiking"]["sac_scale"!="demanding_alpine_hiking"]'
              '["sac_scale"!="difficult_alpine_hiking"]')
VIS_FILTER = '["trail_visibility"!="no"]["trail_visibility"!="horrible"]'
SMOOTH_FILTER = '["smoothness"!="impassable"]["smoothness"!="very_horrible"]["smoothness"!="horrible"]'
TRACK_EXTRA = '["tracktype"!="grade5"]["mtb:scale"!~"^[456]$"]'

OVERPASS_ENDPOINTS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass.openstreetmap.ru/api/interpreter',
]

def tile_coords():
    """Yield (south, west, north, east) for each tile."""
    lat = BBOX_S
    while lat < BBOX_N:
        lng = BBOX_W
        while lng < BBOX_E:
            yield (round(lat, 2), round(lng, 2),
                   round(lat + TILE_SIZE, 2), round(lng + TILE_SIZE, 2))
            lng += TILE_SIZE
        lat += TILE_SIZE

def tile_filename(s, w, n, e):
    return os.path.join(OUT_DIR, f'{s:.2f}_{w:.2f}.json.gz')

def build_query(s, w, n, e):
    af = ACCESS_FILTER + MOTOR_FILTER + MOTO_FILTER + SAC_FILTER + VIS_FILTER + SMOOTH_FILTER
    bbox = f'{s},{w},{n},{e}'
    q = (
        '[out:json][timeout:180][maxsize:300000000];('
        f'way["highway"="track"]{af}{TRACK_EXTRA}({bbox});'
        f'way["highway"="unclassified"]{af}({bbox});'
        f'way["highway"="tertiary"]({bbox});'
        f'way["highway"="secondary"]({bbox});'
        f'way["highway"="primary"]({bbox});'
        f'way["highway"="residential"]["access"!="private"]["access"!="no"]({bbox});'
        ');out geom;'
    )
    return q

def fetch_tile(s, w, n, e, endpoint_idx=0, retry=0):
    query = build_query(s, w, n, e)
    url = OVERPASS_ENDPOINTS[endpoint_idx % len(OVERPASS_ENDPOINTS)]
    data = urllib.parse.urlencode({'data': query}).encode() if False else None
    req = urllib.request.Request(
        url, data=('data=' + urllib.parse.quote(query)).encode(),
        headers={'Content-Type': 'application/x-www-form-urlencoded',
                 'User-Agent': 'road-trip-2026-local-cache/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.load(resp)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as ex:
        if retry < 5:
            wait = 10 * (retry + 1)
            print(f'    retry {retry+1} after {wait}s due to {type(ex).__name__}: {ex}', flush=True)
            time.sleep(wait)
            # Rotate endpoint on network/HTTP failure
            return fetch_tile(s, w, n, e, endpoint_idx + 1, retry + 1)
        raise

import urllib.parse

def main():
    all_tiles = list(tile_coords())
    total = len(all_tiles)
    print(f'Total tiles to fetch: {total} ({TILE_SIZE}° each), bbox [{BBOX_S},{BBOX_W}] → [{BBOX_N},{BBOX_E}]')

    existing = sum(1 for s,w,n,e in all_tiles if os.path.exists(tile_filename(s,w,n,e)))
    print(f'Already downloaded: {existing}. To fetch: {total - existing}.')

    t0 = time.time()
    total_ways = 0
    total_bytes = 0
    for i, (s, w, n, e) in enumerate(all_tiles, 1):
        fn = tile_filename(s, w, n, e)
        if os.path.exists(fn):
            continue
        attempt_start = time.time()
        try:
            data = fetch_tile(s, w, n, e)
        except Exception as ex:
            print(f'[{i}/{total}] FAIL {s:.2f},{w:.2f}: {ex}', flush=True)
            continue
        ways = data.get('elements') or []
        # Keep only what our graph uses: tags + geometry + id + type
        slim = []
        for el in ways:
            if el.get('type') != 'way':
                continue
            slim.append({
                'id': el.get('id'),
                'tags': el.get('tags', {}),
                'geometry': el.get('geometry', []),
            })
        payload = json.dumps({'bbox': [s, w, n, e], 'ways': slim}, separators=(',', ':'))
        with gzip.open(fn, 'wt', encoding='utf-8', compresslevel=6) as f:
            f.write(payload)
        sz = os.path.getsize(fn)
        total_bytes += sz
        total_ways += len(slim)
        dt = time.time() - attempt_start
        elapsed = time.time() - t0
        remaining = (total - i) * elapsed / max(i, 1)
        print(f'[{i}/{total}] {s:.2f},{w:.2f} → {len(slim)} ways, {sz/1024:.0f} KB ({dt:.1f}s). '
              f'Total {total_ways} ways, {total_bytes/1024/1024:.1f} MB. ETA ~{remaining/60:.0f} min.', flush=True)
        # Rate limit: be a good citizen. Overpass wants ~1-2 req/s; we go slower.
        time.sleep(3)

    print(f'\nDone. Total ways: {total_ways}, total size: {total_bytes/1024/1024:.1f} MB, elapsed: {(time.time()-t0)/60:.1f} min')

if __name__ == '__main__':
    main()
