#!/usr/bin/env python3
"""
Download all amenity=fuel nodes (gas stations) in the Alps bbox.
Tile-based to avoid Overpass timeouts on the full bbox.
Saves as alps_fuel.json (uncompressed — small enough).
"""
import json, time, urllib.request, urllib.parse, urllib.error, os, sys

BBOX_S, BBOX_W, BBOX_N, BBOX_E = 43.0, 5.0, 48.0, 16.0
TILE = 1.0  # 1° tiles — fuel stations are sparse, can use bigger tiles
OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alps_fuel.json')

OVERPASS_ENDPOINTS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass.openstreetmap.ru/api/interpreter',
]

def fetch(query, endpoint_idx=0, retry=0):
    url = OVERPASS_ENDPOINTS[endpoint_idx % len(OVERPASS_ENDPOINTS)]
    req = urllib.request.Request(
        url, data=('data=' + urllib.parse.quote(query)).encode(),
        headers={'Content-Type': 'application/x-www-form-urlencoded',
                 'User-Agent': 'road-trip-2026-fuel/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.load(resp)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as ex:
        if retry < 4:
            wait = 8 * (retry + 1)
            print(f'  retry {retry+1} after {wait}s: {ex}', flush=True)
            time.sleep(wait)
            return fetch(query, endpoint_idx + 1, retry + 1)
        raise

def main():
    all_fuels = []
    seen_ids = set()
    tiles = []
    s = BBOX_S
    while s < BBOX_N:
        w = BBOX_W
        while w < BBOX_E:
            tiles.append((s, w, min(s + TILE, BBOX_N), min(w + TILE, BBOX_E)))
            w += TILE
        s += TILE
    print(f'Plan: {len(tiles)} tiles of {TILE}°', flush=True)

    t0 = time.time()
    for i, (ts, tw, tn, te) in enumerate(tiles, 1):
        bbox = f'{ts},{tw},{tn},{te}'
        query = (
            '[out:json][timeout:120];('
            f'node["amenity"="fuel"]({bbox});'
            f'way["amenity"="fuel"]({bbox});'
            ');out center;'
        )
        try:
            data = fetch(query)
        except Exception as ex:
            print(f'[{i}/{len(tiles)}] {ts:.1f},{tw:.1f}: FAIL {ex}', flush=True)
            continue
        added = 0
        for el in (data.get('elements') or []):
            elid = f"{el.get('type')}/{el.get('id')}"
            if elid in seen_ids:
                continue
            seen_ids.add(elid)
            if el.get('type') == 'node':
                lat, lng = el.get('lat'), el.get('lon')
            else:
                c = el.get('center') or {}
                lat, lng = c.get('lat'), c.get('lon')
            if lat is None or lng is None:
                continue
            tags = el.get('tags') or {}
            all_fuels.append({
                'lat': lat, 'lng': lng, 'type': 'fuel',
                'name': tags.get('name') or tags.get('brand') or 'Gas station',
                'brand': tags.get('brand', ''),
                'opening_hours': tags.get('opening_hours', ''),
            })
            added += 1
        elapsed = time.time() - t0
        eta = (len(tiles) - i) * elapsed / max(i, 1) / 60
        print(f'[{i}/{len(tiles)}] {ts:.1f},{tw:.1f} → +{added}, total={len(all_fuels)} (ETA {eta:.1f} min)', flush=True)
        time.sleep(2)

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_fuels, f, ensure_ascii=False, separators=(',', ':'))
    sz = os.path.getsize(OUT_FILE) / 1024
    print(f'\nDone. {len(all_fuels)} fuel stations, {sz:.0f} KB → {OUT_FILE}', flush=True)

if __name__ == '__main__':
    main()
