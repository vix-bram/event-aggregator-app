"""
GT Campus Calendar scraper — Milestone 1.

What this script does, step by step:
1. Downloads the HTML for https://calendar.gatech.edu/
2. Finds a special <script> tag Drupal (the site's CMS) embeds on every
   page called "drupalSettings". It's just a big JSON blob of config data
   the page's JavaScript uses to set itself up.
3. Inside that JSON blob, the calendar widget (FullCalendar.js) has already
   been handed a full list of upcoming events to render. We don't need to
   run a browser or any JavaScript ourselves — the event data is just
   sitting there in the page source as JSON.
4. Each event's data includes a chunk of raw HTML (its title/description
   card). We parse that mini-HTML with BeautifulSoup to pull out clean
   fields: name, date/time, location, description, and category tags.
5. We print every event we found to the terminal in a readable format.
6. (Milestone 2) We also save every event to events.json in the project
   root, so the next scripts (locate.py, map.html) can read structured
   data instead of terminal text.

Why this approach instead of Playwright/browser automation:
The event data is server-rendered into the page as JSON, so a simple HTTP
GET + JSON parsing gets us everything without the extra complexity (and
slowness) of driving a real browser. If GT ever changes their site so the
events are fetched via a separate AJAX call instead, we'd switch to
Playwright then — but for now, this is simpler and more reliable.
"""

import html
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Some event text on the GT calendar contains Unicode characters (fancy
# spaces, em-dashes, etc.) that Windows terminals can't always display,
# because they default to an older encoding (cp1252) instead of UTF-8.
# Without this, printing those characters crashes the script. Reconfiguring
# stdout to UTF-8 with errors="replace" means any character the terminal
# truly can't show gets swapped for a placeholder instead of crashing.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CALENDAR_URL = "https://calendar.gatech.edu/"

# Where the structured output goes: <project root>/events.json.
# Path(__file__) is this script's own location (scraper/), so .parent.parent
# is the project root no matter which folder you run the script from.
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "events.json"

# Georgia Tech's server will reject requests that don't look like they're
# coming from a real browser, so we send a normal-looking User-Agent header.
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def fetch_calendar_html(url: str) -> str:
    """Download the raw HTML for the calendar page."""
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
    response.raise_for_status()  # crash loudly if the page didn't load
    return response.text


def extract_events(html: str) -> list[dict]:
    """
    Pull the list of raw event dicts out of the page's embedded JSON.

    The relevant data lives at:
        drupalSettings -> fullCalendarView[0] -> calendar_options -> events

    "calendar_options" is itself a JSON string *inside* the outer JSON, so
    it has to be parsed a second time.
    """
    soup = BeautifulSoup(html, "html.parser")
    settings_tag = soup.find("script", {"data-drupal-selector": "drupal-settings-json"})
    if settings_tag is None:
        raise RuntimeError(
            "Couldn't find the drupalSettings script tag — the site's "
            "page structure may have changed."
        )

    settings = json.loads(settings_tag.string)
    calendar_config = settings["fullCalendarView"][0]
    calendar_options = json.loads(calendar_config["calendar_options"])
    return calendar_options["events"]


def clean_text(text: str) -> str:
    """
    Tidy up one piece of text from the calendar.

    - html.unescape turns leftover HTML entities back into real characters.
      Some GT event text is escaped twice, so after BeautifulSoup decodes it
      once we still see things like "Ford ES&amp;T"; this fixes it to
      "Ford ES&T".
    - The regex collapses runs of whitespace (including line breaks and
      non-breaking spaces) into a single space, and strip() trims the ends.
      That's what made some category names appear twice in Milestone 1,
      e.g. "Career/Professional development" vs. the same text with extra
      spaces.
    """
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_event(raw_event: dict) -> dict:
    """
    Turn one raw event dict (with an embedded HTML blob) into clean,
    structured fields we can print or, later, hand to the database.
    """
    # "des" holds a small HTML snippet with the event's title, date/time,
    # location, description, and category tags all mixed together.
    card = BeautifulSoup(raw_event.get("des", ""), "html.parser")

    name_tag = card.find("h3")
    name = clean_text(name_tag.get_text()) if name_tag else "(untitled event)"

    description_tag = card.select_one(".event-title-wrapper + div p")
    description = clean_text(description_tag.get_text()) if description_tag else ""

    location = ""
    location_icon = card.select_one(".fa-map-marker")
    if location_icon is not None:
        # The location text sits in the same <div> as the icon, right
        # after it, so grab the whole div's text and drop the icon itself.
        location_div = location_icon.find_parent("div")
        location = clean_text(location_div.get_text())

    categories = []
    for tag in card.select(".event-categories"):
        category = clean_text(tag.get_text())
        if category and category not in categories:  # skip blanks and repeats
            categories.append(category)

    event_url = raw_event.get("url", "")
    if event_url and not event_url.startswith("http"):
        event_url = CALENDAR_URL.rstrip("/") + event_url

    start = raw_event.get("start", "")

    # FullCalendar marks all-day events with "allDay". If GT's data doesn't
    # include that field, fall back to a guess: an event "starting" at
    # exactly midnight is almost always an all-day event (holidays,
    # exhibits) rather than something that truly begins at 12:00 a.m.
    all_day = bool(raw_event.get("allDay")) or start.endswith("T00:00:00")

    return {
        "name": name,
        "start": start,
        "end": raw_event.get("end", ""),
        "all_day": all_day,
        "location": location,
        "description": description,
        "categories": categories,
        "url": event_url,
    }


def print_event(event: dict, index: int) -> None:
    """Print one event to the terminal in a readable, labeled format."""
    print(f"[{index}] {event['name']}")
    print(f"    When:     {event['start']}")
    if event["location"]:
        print(f"    Where:    {event['location']}")
    if event["categories"]:
        print(f"    Category: {', '.join(event['categories'])}")
    if event["description"]:
        print(f"    Details:  {event['description']}")
    print(f"    Link:     {event['url']}")
    print()


def save_events(events: list[dict], path: Path) -> None:
    """
    Write all events to a JSON file.

    encoding="utf-8" and ensure_ascii=False keep characters like curly
    quotes and em-dashes readable in the file, instead of the garbled
    "ΓÇÖ"-style text you get from a PowerShell redirect.
    indent=2 makes the file easy to read by eye.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)


def main() -> None:
    print(f"Fetching {CALENDAR_URL} ...")
    html = fetch_calendar_html(CALENDAR_URL)

    raw_events = extract_events(html)
    print(f"Found {len(raw_events)} events embedded in the page.\n")

    events = [parse_event(raw_event) for raw_event in raw_events]
    for index, event in enumerate(events, start=1):
        print_event(event, index)

    save_events(events, OUTPUT_PATH)
    print(f"Saved {len(events)} events to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
