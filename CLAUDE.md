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
4. Google Maps JavaScript API key, restricted to localhost (a browser key is visible in the page, so the restriction is what protects it)
5. `map.html`: plain HTML page that loads `events.json` and shows pins with popups (open it via `python -m http.server`, since browsers block loading local files from `file://`)

**After that:** time filter and color-coded pins; then decide (rules vs. LLM) for unmatched locations and the free-food tag; then Firebase storage; then more sources.

## Repository Notes

* Git repo on branch `main`, pushed to GitHub at `git@github.com:vix-bram/event-aggregator-app.git` (account `vix-bram`, SSH auth)
* `.gitignore` excludes `venv/`, `events_output.txt` (regenerated by running the scraper), `.env` files (API keys go here — never commit them), and `.claude/settings.local.json`

