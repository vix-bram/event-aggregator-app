# Campus Event Aggregator — Project Overview

## The Problem

Campus events at Georgia Tech are scattered across dozens of sources: department websites, student organization pages, athletics calendars, and more. Students miss events simply because the information is fragmented and hard to track.

## The Goal

Build a web app that automatically scrapes publicly available Georgia Tech webpages for event information, parses it into structured data (plain code where the page is structured; an LLM only where plain code isn't enough), stores it in a database, and displays events as color-coded pins on an interactive Google Maps interface of the GT campus.

## Core Features

* **Automated scraping**: A scheduled job visits a list of known GT event pages on a recurring basis (e.g. every 6 hours) and extracts raw text
* **Parsing**: Turn each source into structured event data (name, date, time, location, description, category). Structured sources like calendar.gatech.edu are parsed with plain Python; an LLM (e.g. Gemini) is reserved for messy sources or fields rules can't handle
* **Location matching**: Free-text locations ("Room 357, Clough Undergraduate Learning Commons") are matched to a campus building with known coordinates so they can be pinned
* **Database storage**: Parsed events are stored in Firebase so the app doesn't have to re-scrape every time a user opens it
* **Map interface**: Events are displayed as pins on a Google Map centered on the GT campus, color-coded by category (e.g. free food, social, professional, sports)
* **Time filtering**: Users can set a specific date and time to see only events happening at that time (e.g. "show me events on Thursday at 4pm")
* **Event popups**: Tapping a pin shows a card with event details (name, time, location, description, registration required or not)

## Event Categories

* Free food
* Social
* Professional / career
* Sports / recreation
* Academic / lecture
* Arts / culture
* Registration required (flag, not a category)

## Tech Stack

* **Scraping**: Python with BeautifulSoup or Playwright
* **Parsing**: Python (BeautifulSoup + JSON) for structured sources; Google Gemini API later, only if needed
* **Database**: Firebase (Firestore)
* **Frontend**: Plain HTML + Google Maps JavaScript API for the prototype; React later
* **Hosting**: Vercel
* **Scheduling**: GitHub Actions or Google Cloud Scheduler

## Target Scrape Sources (Georgia Tech)

* GT Campus Calendar: https://calendar.gatech.edu
* GT Student Engagement (Corq/Engage): https://gatech.campuslabs.com/engage/events
* GT Athletics: https://ramblinwreck.com
* Individual department event pages (to be expanded over time)

## Build Approach

* Start simple: get one scraper working, then get its events onto a map, then the database, then more sources (adding an LLM only where needed)
* Prioritize a working prototype over a polished product
* Each component should be buildable and testable independently before integrating

## Current Status

**Milestone 1 (complete):** A working Python scraper for calendar.gatech.edu that prints structured event data to the terminal. See `milestones/milestone1_summary.txt` for details.

* Code lives in `scraper/gt_calendar_scraper.py`
* It uses `requests` + BeautifulSoup only — no Playwright needed. The calendar page embeds its events as JSON inside a Drupal `drupalSettings` script tag (path: `fullCalendarView[0].calendar_options.events`), so a plain HTTP GET gets everything
* Each event has an HTML snippet (`des`) that is parsed for name, location, description, and category tags; `start` and `url` come straight from the JSON
* Run it with: `venv\Scripts\python scraper\gt_calendar_scraper.py`

**Decision: no LLM for calendar.gatech.edu.** The scraper already gets clean fields from embedded JSON, so an LLM would add cost and randomness without improving the data. The real problems are location text (free-form, room-level, sometimes Online/TBD) and categories (GT's tags don't match ours; no free-food tag). Try keyword rules first, measure what they miss, and only then consider an LLM.

**Milestone 2 (in progress):** Show the next 10 upcoming events as clickable pins on a map. See `milestones/milestone2_summary.txt` for the full plan.

1. Scraper also writes `events.json` (UTF-8, HTML entities unescaped, category names trimmed, `all_day` flag for midnight starts)
2. `data/gt_buildings.json`: ~15–20 buildings with keywords and lat/lng (coordinates taken by hand from Google Maps)
3. `locate.py`: matches each event's location to a building, marks Online/Virtual/TBD as unmappable, prints a match-rate summary
4. Google Maps JavaScript API key, restricted to localhost (a browser key is visible in the page, so the restriction is what protects it). The key goes in `config.js` (gitignored); `config.example.js` is the committed template
5. `map.html`: plain HTML page that loads `events.json` and shows pins with popups (open it via `python -m http.server`, since browsers block loading local files from `file://`)

**Decision (2026-10-22): use GT's RSS feeds instead of scraping the calendar page**, because automated scraping may violate GT's policies, while the feeds are published for reuse. `scraper/gt_calendar_rss.py` now writes `events.json`; `scraper/gt_calendar_scraper.py` is kept for reference only and is no longer run.

* Feeds are listed at https://calendar.gatech.edu/rss-feeds (`/taxonomy/term/<id>/feed`, one per category). Each item's description is the event page as HTML with labeled sections (Event time, Location, Fee, Extras, Invited audience, ...); times are UTC and converted to America/New_York (needs the `tzdata` package on Windows)
* Extras gives a real "Free food" tag (`free_food` field), which the old scraper didn't have
* Known feed problems, to be reported to GT by email: Student sponsored (term 19) returns a PHP out-of-memory error; Special event (17) is empty; the Seminar/Lecture/Colloquium link points to the Conference/Symposium feed (14), though the real seminar feed exists at term 16 (found by the user, now in `FEEDS`); uncategorized events are in no feed. Before adding term 16, the feeds covered only ~40% of the upcoming events the page scraper found (164 of 422 on 2026-10-22)
* The user is also asking GT whether it has an official list of buildings with coordinates
* A pre-save sanity check stops the run (and keeps the old `events.json`) if 0 events are found or most lack a name or location

**Checking building coordinates:** each building in `data/gt_buildings.json` has a `source` (`approximate` = Claude's unverified estimate, `wikipedia`, `google_maps` = picked by the user). The user checks them by eye on `map.html`, where "Show all building points" colors the dots by source (red = unverified). When the user sends a corrected coordinate, set that building's `source` to `google_maps`. Places too far away for the campus map (e.g. R. Randall Rollins at Emory) get `"off_campus": true`: `locate.py` labels their events `off_campus` (no lat/lng) and the map lists them in an "Off campus" section instead of pinning them.

**Product rule (user, 2026-10-24): users must be able to see every event GT publishes in their chosen time frame, not just the ones we can pin.** Events that are online, have no location, or whose location can't be matched (e.g. Chapin, Holland Plant, whose positions the user doesn't know) will go in a separate list in the app, showing whatever the RSS feed gives. Don't guess coordinates for unknown places to force them onto the map.

## Milestone Checklists

Tick items as they're done (`[x]`). A milestone is finished when every item is ticked and its "Done when" is true; then write its `milestones/milestoneN_summary.txt` and move on. Order can change if the user decides so.

### Milestone 2: Events on a map (almost done)
Done when: `map.html` shows the next 10 events as correctly placed pins with popups, lists every unpinnable event in the same time frame, and the location match rate is known.

- [x] RSS reader writes `events.json` (dedupe across feeds, upcoming only, sanity check)
- [x] `locate.py` matches locations to buildings and reports the match rate (~81% of in-person events)
- [x] `map.html`: pins grouped by building, popups, building dots colored by coordinate source
- [x] Panel listing online / unmatched / no-location events for the same time frame as the pins
- [x] Corrected the buildings flagged as wrong (2026-10-24)
- [x] Add the user's new locations from `building_loc.txt` to `gt_buildings.json` (2026-10-24; match rate now 86%)
- [x] Check the remaining `approximate` (red) buildings by eye on the map (2026-10-24; all 57 buildings now checked by the user)
- [ ] Email GT about the feed problems and the building list (draft written 2026-10-24)
- [ ] Screenshot of the map in the README
- [ ] Write `milestones/milestone2_summary.txt` as complete

### Milestone 3: Filters and categories
Done when: a user can pick a day and time and see only the events happening then, on the map and in the list, with pins colored by our categories.

- [ ] Date/time filter; pins and the unmapped panel both follow it (replaces "next 10 events")
- [ ] Map GT's categories to ours (free food, social, professional, sports, academic, arts) with keyword rules; free food comes from the feed's Extras field
- [ ] Registration-required flag (e.g. from related links like "Register" / "RSVP"); measure how often the rule is wrong
- [ ] Color-coded pins by category, with a legend
- [ ] Popups show category, free food and registration
- [ ] Measure the unmatched locations again; decide rules vs. LLM (default: rules)

### Milestone 4: Automatic updates and a public site
Done when: a public URL shows events that refresh on their own every ~6 hours, and a failed refresh sends an email.

- [ ] GitHub Actions job runs `gt_calendar_rss.py` + `locate.py` on a schedule (the sanity check makes a broken run fail visibly)
- [ ] Deploy to Vercel
- [ ] Google Maps key restricted to the deployed domain (plus localhost for development)
- [ ] Live demo link in the README

### Milestone 5: Database (Firebase)
Done when: events are stored in Firestore and the site reads them from there.

- [ ] Decide first whether it's needed: for read-only data refreshed every few hours, a static `events.json` may be enough. Firestore earns its place once there are user features (saved events, accounts) or many sources
- [ ] Firestore schema; scheduled job writes events there
- [ ] Site reads from Firestore

### Milestone 6: More sources
Done when: events from at least one more source appear alongside the calendar's, without duplicates.

- [ ] Engage (gatech.campuslabs.com): check for an official feed/API and its terms first, as with the calendar
- [ ] GT Athletics (ramblinwreck.com)
- [ ] Remove duplicates across sources (same event posted in two places)
- [ ] LLM only for sources plain parsing can't handle

## Repository Notes

* Git repo on branch `main`, pushed to GitHub at `git@github.com:vix-bram/event-aggregator-app.git` (account `vix-bram`, SSH auth)
* `.gitignore` excludes `venv/`, `events_output.txt` (regenerated by running the scraper), `.env` files (API keys go here — never commit them), and `.claude/settings.local.json`

