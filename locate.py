"""
Location matcher — Milestone 2.

What this script does, step by step:
1. Reads events.json (written by scraper/gt_calendar_rss.py) and
   data/gt_buildings.json (our hand-made list of campus buildings).
2. For each event, looks for a building keyword inside its free-text
   location, e.g. "Room 357, Clough Undergraduate Learning Commons"
   contains "clough", so it gets Clough's coordinates.
3. Labels every event with a location_status:
     matched      -> found a building; lat/lng added
     online       -> Online / Virtual / TBD etc., nothing to pin
     unmatched    -> has a location, but no keyword matched (yet)
     no_location  -> the event didn't list a location at all
4. Saves the labeled events back to events.json and prints a summary,
   including the most common unmatched locations. That list is your
   to-do list for adding buildings or keywords.

Run it after the RSS reader:
    venv\\Scripts\\python scraper\\gt_calendar_rss.py
    venv\\Scripts\\python locate.py
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent
EVENTS_PATH = PROJECT_ROOT / "events.json"
BUILDINGS_PATH = PROJECT_ROOT / "data" / "gt_buildings.json"

# If a location contains one of these and no building, there's nothing to
# put on the map. Buildings are checked first, so a hybrid event like
# "CODA Building 9th floor Atrium & Virtual" still gets pinned at CODA.
ONLINE_KEYWORDS = [
    "online", "virtual", "zoom", "teams", "discord", "webinar", "hybrid",
    "tbd", "tba", "related link", "registration required",
    "georgia tech campus", "off-site", "vitual", "various",
]


def normalize(text: str) -> str:
    """Lowercase and straighten curly apostrophes (O’Keefe -> o'keefe)."""
    return text.lower().replace("’", "'").replace("‘", "'")


def contains_keyword(text: str, keyword: str) -> bool:
    """
    True if keyword appears in text as a whole word/phrase.

    The lookarounds stop short keywords from matching inside longer words:
    "crc" won't match "crcl", and "petit" won't match "Pettit" (a different
    building).
    """
    pattern = r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None


def find_building(location: str, buildings: list[dict]) -> dict | None:
    """Return the first building whose keyword appears in the location."""
    text = normalize(location)
    for building in buildings:
        for keyword in building["keywords"]:
            if contains_keyword(text, normalize(keyword)):
                return building
    return None


def locate_event(event: dict, buildings: list[dict]) -> None:
    """Add building, lat, lng and location_status to one event (in place)."""
    event["building"] = None
    event["lat"] = None
    event["lng"] = None

    location = event.get("location", "")
    if not location:
        event["location_status"] = "no_location"
        return

    building = find_building(location, buildings)
    if building is not None:
        event["building"] = building["name"]
        event["lat"] = building["lat"]
        event["lng"] = building["lng"]
        event["location_status"] = "matched"
    elif any(contains_keyword(normalize(location), k) for k in ONLINE_KEYWORDS):
        event["location_status"] = "online"
    else:
        event["location_status"] = "unmatched"


def print_summary(events: list[dict]) -> None:
    statuses = Counter(e["location_status"] for e in events)
    total = len(events)
    print(f"Located {total} events:")
    for status in ["matched", "unmatched", "online", "no_location"]:
        count = statuses[status]
        print(f"  {status:<12} {count:>4}  ({count / total:.0%})")

    in_person = statuses["matched"] + statuses["unmatched"]
    if in_person:
        print(f"\nMatch rate for in-person events: "
              f"{statuses['matched'] / in_person:.0%}")

    unmatched = Counter(
        e["location"] for e in events if e["location_status"] == "unmatched"
    )
    if unmatched:
        print("\nMost common unmatched locations (add keywords or buildings for these):")
        for location, count in unmatched.most_common(15):
            print(f"  {count:>3}  {location}")

    buildings = Counter(e["building"] for e in events if e["building"])
    print("\nEvents per building:")
    for building, count in buildings.most_common():
        print(f"  {count:>3}  {building}")


def main() -> None:
    events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    buildings = json.loads(BUILDINGS_PATH.read_text(encoding="utf-8"))

    for event in events:
        locate_event(event, buildings)

    with open(EVENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

    print_summary(events)
    print(f"\nSaved located events to {EVENTS_PATH}")


if __name__ == "__main__":
    main()
