"""
GT Campus Calendar RSS reader.

Replaces gt_calendar_scraper.py: instead of pulling data out of the
calendar's web page, this reads the RSS feeds GT publishes for exactly this
kind of reuse (listed at https://calendar.gatech.edu/rss-feeds).

What this script does, step by step:
1. Downloads one RSS feed per event category (one request each, with a
   short pause in between so we're polite to GT's server).
2. Each feed item has a title, a link, and a "description" that is really
   the event's whole page as HTML, with labeled sections:
       Event time / Location / Fee / Extras / Invited audience / ...
   We split the description on those labels and read each section.
3. The same event can be in several feeds (e.g. Arts AND Career), so we
   keep each event once, using its link as the ID.
4. The feeds include events going back years, so we keep only events that
   haven't ended yet.
5. GT sometimes posts the same event twice, as two pages with different
   links (".../volleyball-vs-smu" and ".../volleyball-vs-smu-0"). Events
   with the same name, start time and location are merged into one.
6. Before saving, a sanity check makes sure the result looks sane. If it
   doesn't, the script stops with an error and leaves the old events.json
   alone, so a GT-side change can't silently wipe the map.
7. Saves the events to events.json for locate.py and map.html.

Known feed problems (as of October 2026, reported to GT on 2026-10-24):
- "Student sponsored" returns a PHP out-of-memory error instead of RSS
- "Special event" returns a valid but empty feed
- The "Seminar/Lecture/Colloquium" link on the feeds page points to the
  Conference/Symposium feed (term 14); the real seminar feed is term 16
- Events with no category aren't in any feed
Before the seminar feed (term 16) was added, the feeds covered only ~40%
of the events shown on the calendar's main page.
"""

import html
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FEED_BASE = "https://calendar.gatech.edu/taxonomy/term/{}/feed"

# (category name as shown on https://calendar.gatech.edu/rss-feeds, term ID)
FEEDS = [
    ("Institute/Academic/Religious", 111),  # the feed itself is titled "holidays and observances"
    ("Arts and Performance", 12),
    ("Career/Professional development", 13),
    ("Conference/Symposium", 14),  # "Seminar/Lecture/Colloquium" also links here
    ("Other/Miscellaneous", 15),
    ("Seminar/Lecture/Colloquium", 16),  # the actual feed is 16, but the rss feed links to 14 (Conference/Symposium) instead
    ("Special event", 17),
    ("Sports/Athletics", 18),
    ("Student sponsored", 19),
    ("Training/Workshop", 20),
]

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "events.json"

# Event times in the feeds are in UTC ("...T19:00:00Z"). We convert them to
# campus time so an all-day event reads as starting at 00:00, not 04:00.
CAMPUS_TZ = ZoneInfo("America/New_York")

# We say who we are instead of pretending to be a browser, so GT can see
# where the traffic comes from (and contact us if it's a problem).
REQUEST_HEADERS = {
    "User-Agent": "GT-Event-Map/0.1 (student project; github.com/vix-bram/event-aggregator-app)"
}
SECONDS_BETWEEN_REQUESTS = 2

# The section labels inside each item's description, each on its own line.
# Longer labels come first so "Location URL" isn't read as "Location".
SECTION_LABELS = [
    "Summary sentence", "Summary", "Event time", "Location URL",
    "Location email", "Location phone", "Location", "Fee", "Extras",
    "Associated importer", "Invited audience", "Mercury ID",
    "Source updated", "Groups",
]
SECTION_PATTERN = re.compile(
    r"^\s*(" + "|".join(re.escape(label) for label in SECTION_LABELS) + r")\s*$",
    re.MULTILINE,
)


def clean_text(text: str) -> str:
    """
    Undo leftover HTML entities and collapse whitespace.

    Some GT text is escaped twice, so even after parsing we can still see
    "Scholar&#039;s"; html.unescape turns that into "Scholar's".
    """
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def save_events(events: list[dict], path: Path) -> None:
    """Write events as readable UTF-8 JSON (curly quotes etc. kept as-is)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)


def fetch_feed(term_id: int) -> list[ET.Element] | None:
    """
    Download one feed and return its <item> elements.

    Returns None (instead of crashing) if the feed is broken, so one bad
    feed doesn't stop us from reading the others.
    """
    response = requests.get(FEED_BASE.format(term_id), headers=REQUEST_HEADERS, timeout=30)
    response.raise_for_status()
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        return None
    return root.findall("./channel/item")


def split_sections(description: str) -> dict[str, str]:
    """
    Split a description into {label: section HTML}.

    re.split with a capture group returns
        [text before first label, label, section, label, section, ...]
    so we pair the labels up with the sections that follow them.
    """
    parts = SECTION_PATTERN.split(description)
    return dict(zip(parts[1::2], parts[2::2]))


def section_lines(section_html: str) -> list[str]:
    """The non-empty lines of text in a section."""
    text = BeautifulSoup(section_html, "html.parser").get_text("\n")
    return [clean_text(line) for line in text.split("\n") if clean_text(line)]


def links_under_heading(soup: BeautifulSoup, heading: str) -> list[dict]:
    """
    Return the links listed under an <h4> heading such as "Event categories".

    The markup looks like:
        <div><div><h4>Event categories</h4></div><div> ...links... </div></div>
    so we go up two <div>s from the heading and collect the links inside.
    """
    h4 = soup.find("h4", string=re.compile(rf"^\s*{re.escape(heading)}\s*$"))
    if h4 is None:
        return []
    block = h4.find_parent("div").find_parent("div")
    return [
        {"text": clean_text(a.get_text()), "url": a.get("href", "")}
        for a in block.select("a.hg-link")
    ]


def to_campus_time(utc_string: str) -> datetime:
    """'2026-11-03T19:00:00Z' -> 2026-11-03 14:00 in Atlanta."""
    return datetime.fromisoformat(utc_string.replace("Z", "+00:00")).astimezone(CAMPUS_TZ)


def parse_item(item: ET.Element) -> dict | None:
    """
    Turn one RSS <item> into the same event fields the old scraper made,
    plus a few the feeds give us for free. Returns None for items with no
    event time, since we can't place those on a timeline.
    """
    # ElementTree has already undone the XML escaping, so this is HTML.
    description = item.findtext("description", default="")
    sections = split_sections(description)
    soup = BeautifulSoup(description, "html.parser")

    times = BeautifulSoup(sections.get("Event time", ""), "html.parser").find_all("time")
    if not times:
        return None
    start = to_campus_time(times[0]["datetime"])
    end = to_campus_time(times[1]["datetime"]) if len(times) > 1 else None

    # The first line of the Location section is the place; any lines after
    # it are the organizer's contact details.
    location_lines = section_lines(sections.get("Location", ""))

    # "Extras" holds plain-text tags ("Free food", "Freebies") followed by a
    # block of related links. Drop the link block and keep the tags.
    extras_soup = BeautifulSoup(sections.get("Extras", ""), "html.parser")
    for div in extras_soup.find_all("div"):
        div.decompose()
    extras = section_lines(str(extras_soup))

    fee_lines = section_lines(sections.get("Fee", ""))
    summary_lines = section_lines(sections.get("Summary sentence", ""))

    categories = []
    for link in links_under_heading(soup, "Event categories"):
        if link["text"] and link["text"] not in categories:
            categories.append(link["text"])

    return {
        "name": clean_text(item.findtext("title", default="")) or "(untitled event)",
        "start": start.isoformat(),
        "end": end.isoformat() if end else "",
        # A midnight start in campus time means an all-day event
        # (holidays, exhibits), not something that begins at 12:00 a.m.
        "all_day": (start.hour, start.minute) == (0, 0),
        "location": location_lines[0] if location_lines else "",
        "description": " ".join(summary_lines),
        "categories": categories,
        "free_food": "Free food" in extras,
        "extras": extras,
        "fee": fee_lines[0] if fee_lines else "",
        "audience": section_lines(sections.get("Invited audience", "")),
        "related_links": links_under_heading(soup, "Related links"),
        "url": item.findtext("link", default="").strip(),
    }


def check_events(events: list[dict]) -> None:
    """
    Stop with an error if the results look broken, e.g. because GT changed
    the feed format and our parsing quietly stopped finding things.
    """
    if not events:
        raise RuntimeError("No upcoming events found in any feed. Not overwriting events.json.")
    unnamed = sum(e["name"] == "(untitled event)" for e in events)
    no_location = sum(not e["location"] for e in events)
    if unnamed > len(events) / 2 or no_location > len(events) / 2:
        raise RuntimeError(
            f"{unnamed} of {len(events)} events have no name and {no_location} have no "
            "location. The feed format may have changed. Not overwriting events.json."
        )


def merge_duplicates(events: list[dict]) -> list[dict]:
    """
    Merge events GT posted twice under different links.

    Two events are the same posting if their name, start time and location
    match (ignoring capitalization). We keep the copy with the shorter link,
    which is the original (GT adds "-0", "-1", ... to the copies), and add
    any categories or free-food flag the other copy had, so nothing is lost.
    """
    kept: dict[tuple, dict] = {}
    for event in sorted(events, key=lambda e: len(e["url"])):
        key = (event["name"].lower(), event["start"], event["location"].lower())
        original = kept.get(key)
        if original is None:
            kept[key] = event
            continue
        for category in event["categories"]:
            if category not in original["categories"]:
                original["categories"].append(category)
        original["free_food"] = original["free_food"] or event["free_food"]
    return list(kept.values())


def main() -> None:
    events_by_url: dict[str, dict] = {}
    for index, (category, term_id) in enumerate(FEEDS):
        if index > 0:
            time.sleep(SECONDS_BETWEEN_REQUESTS)
        items = fetch_feed(term_id)
        if items is None:
            print(f"  WARNING  {category:<32} broken feed (not valid RSS), skipped")
            continue
        if not items:
            print(f"  WARNING  {category:<32} feed is empty")
            continue

        added = 0
        for item in items:
            event = parse_item(item)
            if event and event["url"] not in events_by_url:
                events_by_url[event["url"]] = event
                added += 1
        print(f"  ok       {category:<32} {len(items):>4} items, {added:>4} new")

    now = datetime.now(CAMPUS_TZ)
    upcoming = [
        e for e in events_by_url.values()
        if datetime.fromisoformat(e["end"] or e["start"]) >= now
    ]
    before_merge = len(upcoming)
    upcoming = merge_duplicates(upcoming)
    upcoming.sort(key=lambda e: e["start"])

    print(f"\n{len(events_by_url)} unique events in the feeds, {before_merge} not yet ended")
    print(f"  {before_merge - len(upcoming)} duplicate postings merged, {len(upcoming)} events left")
    print(f"  {sum(e['free_food'] for e in upcoming)} upcoming events list free food")

    check_events(upcoming)
    save_events(upcoming, OUTPUT_PATH)
    print(f"Saved {len(upcoming)} events to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
