#!/usr/bin/env python3
"""Build site/buildings.json: outlines of the places named in the course catalogue, from OpenStreetMap.

Run by hand when a building should be added: python3 tools/buildings.py
Each entry maps the catalogue's building name (e.g. "N24" or "45") to the OSM ways/relations that outline it.
"""
import json, pathlib, time, urllib.request

# catalogue name: (map label, other catalogue names, OSM elements)
PLACES = {
    "M23": ("M23", [], ["way/329782186"]),
    "M24": ("M24", [], ["way/329782187"]),
    "M25": ("M25", [], ["way/329782188"]),
    "M26": ("M26", [], ["way/460602804"]),
    "M26.1": ("M26.1", [], ["way/1396461010"]),
    "M28": ("M28", ["TTU"], ["way/639028574"]),  # "To Train U"
    "N24": ("N24", [], ["way/329782192"]),
    "N25": ("N25", [], ["relation/5523395"]),
    "N26": ("N26", [], ["way/329782194"]),
    "N27": ("N27", [], ["relation/11504441"]),
    "O25": ("O25", [], ["way/329782195"]),
    "O26": ("O26", [], ["way/329782196"]),
    "O27": ("O27", [], ["relation/5523241"]),
    "O28": ("O28", [], ["relation/14625516"]),
    "O29": ("O29", [], ["way/101177773"]),
    # Uni West: the catalogue uses the house numbers on Albert-Einstein-Allee.
    "43": ("43", [], ["way/51818809"]),
    "45": ("45", [], ["relation/444096", "way/66767258"]),
    "47": ("47", [], ["way/179943586", "way/51819209"]),
    "Bibliothek": ("Bibliothek", [], ["relation/20451396"]),
    "Barbara Mez-Starck-Haus": ("Mez-Starck", [], ["way/1082095744"]),
    "Chirurgie": ("Chirurgie", [], ["relation/367881"]),
    "Helmholtzstraße 18": ("Helmholtz 18", [], ["way/115626016"]),
    "Helmholtzstraße 22": ("Helmholtz 22", [], ["way/115626014"]),
}
OUT = pathlib.Path(__file__).parent.parent / "site" / "buildings.json"


def osm(element):
    req = urllib.request.Request(f"https://api.openstreetmap.org/api/0.6/{element}/full.json",
                                 headers={"User-Agent": "parkingsim (github.com/raustefan/parkingsim)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        els = json.load(r)["elements"]
    time.sleep(1)  # be gentle with the OSM API
    nodes = {e["id"]: [round(e["lon"], 6), round(e["lat"], 6)] for e in els if e["type"] == "node"}
    ways = {e["id"]: [nodes[n] for n in e["nodes"]] for e in els if e["type"] == "way"}
    main = next(e for e in els if f"{e['type']}/{e['id']}" == element)
    if main["type"] == "way":
        return [ways[main["id"]]], main.get("tags", {})
    # Relations: outer members (or members without a role) are joined into rings; courtyards are drawn filled.
    segs = [ways[m["ref"]] for m in main["members"] if m["type"] == "way" and m["role"] in ("outer", "") and m["ref"] in ways]
    return stitch(segs), main.get("tags", {})


def stitch(segs):
    """Join way segments that share end points into closed rings."""
    segs, rings = [s[:] for s in segs], []
    while segs:
        ring = segs.pop(0)
        while ring[0] != ring[-1]:
            for i, s in enumerate(segs):
                if s[0] == ring[-1]: ring += s[1:]
                elif s[-1] == ring[-1]: ring += s[-2::-1]
                elif s[-1] == ring[0]: ring = s[:-1] + ring
                elif s[0] == ring[0]: ring = s[:0:-1] + ring
                else: continue
                segs.pop(i)
                break
            else:
                break
        rings.append(ring if ring[0] == ring[-1] else ring + ring[:1])
    return rings


features = []
for name, (label, aliases, elements) in PLACES.items():
    rings, title = [], ""
    for element in elements:
        r, tags = osm(element)
        rings += r
        title = title or next((tags[k] for k in ("name", "alt_name") if tags.get(k) and tags[k] != label), "")
    pts = [p for ring in rings for p in ring]
    centre = [round(sum(p[0] for p in pts) / len(pts), 6), round(sum(p[1] for p in pts) / len(pts), 6)]
    features.append({"type": "Feature", "id": name,
                     "properties": {"label": label, "name": title, "aliases": aliases, "centre": centre},
                     "geometry": {"type": "MultiPolygon", "coordinates": [[ring] for ring in rings]}})
    print(name, label, title, [len(r) for r in rings])

OUT.write_text(json.dumps({"type": "FeatureCollection", "attribution": "© OpenStreetMap contributors, ODbL",
                           "features": features}, ensure_ascii=False, separators=(",", ":")))
