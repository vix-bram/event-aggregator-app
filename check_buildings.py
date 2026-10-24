"""
Building coordinate checker.

Our building coordinates in data/gt_buildings.json come from different
places (see each building's "source"), and some are only estimates. This
script compares them with OpenStreetMap (OSM), a free, community-made map
where Georgia Tech's buildings are mapped in detail, so you only have to
check the buildings where the two disagree.

What this script does, step by step:
1. Asks OSM's Overpass API (one request) for every named building and
   place in a box around campus, with each one's center point.
2. For each of our buildings, finds the OSM places whose name contains one
   of the building's keywords (or its name), using the same whole-word
   matching as locate.py. If several match, it uses the closest one.
3. Measures the distance between our point and OSM's, and prints the
   buildings that are more than FLAG_DISTANCE_M apart, with Google Maps
   links to both points so you can see which one is right.

OSM can be wrong too, and the "closest match" can be a different building
with a similar name, so always look at the OSM name it matched before
changing anything. This script only reports; it never edits the file.

Run it with:
    venv\\Scripts\\python check_buildings.py
"""

import json
import math
import re
import sys

import requests

from locate import BUILDINGS_PATH, contains_keyword, normalize

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# A box around campus and Tech Square: (south, west, north, east).
CAMPUS_BOX = (33.765, -84.410, 33.786, -84.384)

# Points farther apart than this get flagged. A large building is roughly
# 50-100 m across, so 50 m usually means the pin is off the building.
FLAG_DISTANCE_M = 50

REQUEST_HEADERS = {
    "User-Agent": "GT-Event-Map/0.1 (student project; github.com/vix-bram/event-aggregator-app)"
}


def fetch_osm_places() -> list[dict]:
    """
    Return [{"name", "lat", "lng", "is_building"}] for named OSM places
    on campus: buildings, plus leisure (fields, gardens) and amenity
    (dining halls, theaters) places that might not be tagged as buildings.

    "out center" makes Overpass give a single center point for building
    outlines, which is what we want to compare against.
    """
    box = ",".join(str(n) for n in CAMPUS_BOX)
    query = f"""
        [out:json][timeout:60];
        (
          nwr["name"]["building"]({box});
          nwr["name"]["leisure"]({box});
          nwr["name"]["amenity"]({box});
        );
        out center tags;
    """
    response = requests.post(OVERPASS_URL, data={"data": query},
                             headers=REQUEST_HEADERS, timeout=90)
    response.raise_for_status()

    places = []
    for element in response.json()["elements"]:
        # Single points ("nodes") have lat/lon directly; outlines ("ways")
        # and groups ("relations") have them under "center".
        point = element.get("center", element)
        if "lat" not in point:
            continue
        places.append({
            "name": element["tags"]["name"],
            "lat": point["lat"],
            "lng": point["lon"],
            "is_building": "building" in element["tags"],
        })
    return places


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Distance in meters between two points. On a campus-sized area the
    Earth is flat enough that simple x/y math is accurate to well under
    a meter.
    """
    meters_per_degree = 111_320
    dy = (lat2 - lat1) * meters_per_degree
    dx = (lng2 - lng1) * meters_per_degree * math.cos(math.radians(lat1))
    return math.hypot(dx, dy)


# Words too common to help tell buildings apart.
FILLER_WORDS = {"building", "the", "of", "and", "at"}


def name_words(text: str) -> set[str]:
    """
    The main words of a name: "D.M. Smith Building" -> {"d", "m", "smith"}.
    Splitting on anything that isn't a letter or digit makes "D.M." and
    "D. M." the same, and dropping filler words makes "&" and "and" the same.
    """
    return set(re.findall(r"[a-z0-9]+", normalize(text).replace("'", ""))) - FILLER_WORDS


def find_osm_match(building: dict, places: list[dict]) -> dict | None:
    """
    The closest OSM place that matches the building, either because its
    name contains one of the building's keywords, or because it contains
    every main word of the building's name (so "Global Learning Center"
    matches "Global Learning & Conference Center"). Places tagged as
    buildings are preferred, so "Clough" matches the building rather than
    a nearby cafe inside it.
    """
    keywords = [normalize(k) for k in building["keywords"]]
    our_words = name_words(building["name"])
    matches = [p for p in places
               if any(contains_keyword(normalize(p["name"]), k) for k in keywords)
               or our_words <= name_words(p["name"])]
    buildings_only = [p for p in matches if p["is_building"]]
    candidates = buildings_only or matches
    if not candidates:
        return None
    return min(candidates, key=lambda p: distance_m(
        building["lat"], building["lng"], p["lat"], p["lng"]))


def maps_link(lat: float, lng: float) -> str:
    return f"https://www.google.com/maps?q={lat:.6f},{lng:.6f}"


def main() -> None:
    buildings = json.loads(BUILDINGS_PATH.read_text(encoding="utf-8"))
    print("Asking OpenStreetMap for campus buildings ...")
    places = fetch_osm_places()
    print(f"Got {len(places)} named places.\n")

    flagged, agreed, not_found = [], [], []
    for building in buildings:
        match = find_osm_match(building, places)
        if match is None:
            not_found.append(building)
            continue
        distance = distance_m(building["lat"], building["lng"], match["lat"], match["lng"])
        (flagged if distance > FLAG_DISTANCE_M else agreed).append((building, match, distance))

    print(f"=== More than {FLAG_DISTANCE_M} m from OpenStreetMap: {len(flagged)} (check these) ===\n")
    for building, match, distance in sorted(flagged, key=lambda row: -row[2]):
        print(f"{building['name']}  [{building['source']}]  {distance:.0f} m off")
        print(f"    OSM matched: {match['name']}")
        print(f"    ours: {maps_link(building['lat'], building['lng'])}")
        print(f"    OSM:  {maps_link(match['lat'], match['lng'])}")
        print()

    print(f"=== Within {FLAG_DISTANCE_M} m of OpenStreetMap: {len(agreed)} ===\n")
    for building, match, distance in sorted(agreed, key=lambda row: -row[2]):
        print(f"  {distance:>3.0f} m  {building['name']}  [{building['source']}]  (OSM: {match['name']})")

    if not_found:
        print(f"\n=== Not found in OpenStreetMap: {len(not_found)} (check by hand) ===\n")
        for building in not_found:
            print(f"  {building['name']}  [{building['source']}]  "
                  f"{maps_link(building['lat'], building['lng'])}")


if __name__ == "__main__":
    main()
