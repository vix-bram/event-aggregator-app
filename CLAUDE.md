# Campus Event Aggregator — Project Overview

## The Problem

Campus events at Georgia Tech are scattered across dozens of sources: department websites, student organization pages, athletics calendars, and more. Students miss events simply because the information is fragmented and hard to track.

## The Goal

Build a mobile app, published on Google Play first and the Apple App Store later, that shows Georgia Tech events as pins, filterable by category, on an interactive map of the GT campus. Behind it, a scheduled job reads publicly available GT event sources, parses them into structured data (plain code where the source is structured; an LLM only where plain code isn't enough) and publishes them to Firebase, where the app reads them.

**Decision (user, 2026-10-29):** the target changed from a web app (on Vercel) to a mobile app. The app is built with Expo (React Native), so one codebase serves Android and iOS, and EAS (Expo's cloud build service) builds the iPhone version without a Mac. Firebase replaces Vercel as the host. Everything is tested free with the Expo Go app on the user's own Android phone and iPhone (plus the Android Studio emulator on the laptop) before paying for any store account (Google Play $25 once; Apple $99/year). Build and test on both platforms from the start, but publish Android first. `map.html` stays as the working prototype and reference for the app's behavior.

## Core Features

* **Automated scraping**: A scheduled job visits a list of known GT event pages once a day (10:00 UTC, early morning in Atlanta; changed from every 6 hours by the user on 2026-10-29) and extracts raw text
* **Parsing**: Turn each source into structured event data (name, date, time, location, description, category). Structured sources like calendar.gatech.edu are parsed with plain Python; an LLM (e.g. Gemini) is reserved for messy sources or fields rules can't handle
* **Location matching**: Free-text locations ("Room 357, Clough Undergraduate Learning Commons") are matched to a campus building with known coordinates so they can be pinned
* **Database storage**: Parsed events are published to Firebase so the app doesn't have to re-scrape every time a user opens it
* **Map interface**: In the mobile app, events are displayed as pins on a map centered on the GT campus, filterable by category with checkboxes (e.g. food, social, professional, sports)
* **Time filtering**: Users can set a specific date and time to see only events happening at that time (e.g. "show me events on Thursday at 4pm")
* **Event popups**: Tapping a pin shows a card with event details (name, time, location, description, registration required or not)

## Event Categories

* Food (whether it is free is for the student to check)
* Social
* Professional / career
* Sports / recreation
* Academic / lecture
* Arts / culture
* Registration required (flag, not a category)

## Tech Stack

* **Scraping**: Python with BeautifulSoup or Playwright
* **Parsing**: Python (BeautifulSoup + JSON) for structured sources; Google Gemini API later, only if needed
* **Data hosting**: Firebase (Firestore, or a static `events.json` on Firebase; decided in Milestone 4)
* **App**: Expo (React Native) for Android and iOS, with a native map (`react-native-maps`); tested with Expo Go and the Android Studio emulator; store builds via EAS
* **Prototype**: Plain HTML + Google Maps JavaScript API (`map.html`)
* **Scheduling**: GitHub Actions

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

**Milestone 2 (complete, 2026-10-24):** Show the next 10 upcoming events as clickable pins on a map. See `milestones/milestone2_summary.txt` for what was built, results and open issues. The numbered plan below is how it started; the RSS decision further down changed step 1.

1. Scraper also writes `events.json` (UTF-8, HTML entities unescaped, category names trimmed, `all_day` flag for midnight starts)
2. `data/gt_buildings.json`: ~15–20 buildings with keywords and lat/lng (coordinates taken by hand from Google Maps)
3. `locate.py`: matches each event's location to a building, marks Online/Virtual/TBD as unmappable, prints a match-rate summary
4. Google Maps JavaScript API key, restricted to localhost (a browser key is visible in the page, so the restriction is what protects it). The key goes in `config.js` (gitignored); `config.example.js` is the committed template
5. `map.html`: plain HTML page that loads `events.json` and shows pins with popups (open it via `python -m http.server`, since browsers block loading local files from `file://`)

**Decision (2026-10-22): use GT's RSS feeds instead of scraping the calendar page**, because automated scraping may violate GT's policies, while the feeds are published for reuse. `scraper/gt_calendar_rss.py` now writes `events.json`; `scraper/gt_calendar_scraper.py` is kept for reference only and is no longer run. It is gitignored (removed from GitHub on 2026-10-28; the user keeps it locally).

* Feeds are listed at https://calendar.gatech.edu/rss-feeds (`/taxonomy/term/<id>/feed`, one per category). Each item's description is the event page as HTML with labeled sections (Event time, Location, Fee, Extras, Invited audience, ...); times are UTC and converted to America/New_York (needs the `tzdata` package on Windows)
* Extras gives a real "Free food" tag (`free_food` field), which the old scraper didn't have
* Known feed problems, to be reported to GT by email: Student sponsored (term 19) returns a PHP out-of-memory error; Special event (17) is empty; the Seminar/Lecture/Colloquium link points to the Conference/Symposium feed (14), though the real seminar feed exists at term 16 (found by the user, now in `FEEDS`); uncategorized events are in no feed. Before adding term 16, the feeds covered only ~40% of the upcoming events the page scraper found (164 of 422 on 2026-10-22)
* The user is also asking GT whether it has an official list of buildings with coordinates
* A pre-save sanity check stops the run (and keeps the old `events.json`) if 0 events are found or most lack a name or location

**Checking building coordinates:** each building in `data/gt_buildings.json` has a `source` (`approximate` = Claude's unverified estimate, `wikipedia`, `google_maps` = picked by the user). The user checks them by eye on `map.html`, where "Show all building points" colors the dots by source (red = unverified). When the user sends a corrected coordinate, set that building's `source` to `google_maps`. `locate.py` uses the first building in the file whose keyword matches, so a specific building goes before a broader one that shares a word (e.g. Scheller Tower, added 2026-10-26, sits before Technology Square, whose keyword `scheller` used to catch it). Places too far away for the campus map (e.g. R. Randall Rollins at Emory) get `"off_campus": true`: `locate.py` labels their events `off_campus` (no lat/lng) and the map lists them in an "Off campus" section instead of pinning them.

**Product rule (user, 2026-10-24): users must be able to see every event GT publishes in their chosen time frame, not just the ones we can pin.** Events that are online, have no location, or whose location can't be matched (e.g. Chapin, Holland Plant, whose positions the user doesn't know) will go in a separate list in the app, showing whatever the RSS feed gives. Don't guess coordinates for unknown places to force them onto the map.

**Milestone 3 (complete, 2026-10-28; see `milestones/milestone3_summary.txt`):** pipeline is now `scraper/gt_calendar_rss.py` → `locate.py` → `categorize.py` → `map.html`.

* The RSS reader also stores `details` (the event's full write-up), used only by `categorize.py` for registration/food clues
* `categorize.py` sets `our_categories`: every category that fits (food, social, professional, sports, academic, arts, other), with `category_reasons` naming the rule behind each. It also sets `registration_required` (register/RSVP/sign up/tickets in links, location, fee or write-up; "Registrar" doesn't match) with `registration_reason`. Name keywords catch what GT's vague tags miss. GT's broad tags (Training/Workshop, Student sponsored) count only when nothing else matched. Holidays and closures fall to `other` on purpose
* **"Food", not "free food" (user, 2026-10-26):** whether food is free (or only for registered people) is for the student to check on the event page. Food comes from GT's "Free food" Extras tag, food words in the name, or "lunch will be served"-style phrases. The RSS reader's `free_food` field stays as GT's raw tag
* Tickets count as "registration required" (sports games)
* **Map design (user, 2026-10-26; colors and layout changed 2026-10-28):** no category colors. All pins are GT gold `#B3A369` with navy `#003057` border and number (as in Milestone 2); the category bar is gold too, and the "Not on the map" panel sits left of the map. Students tick category checkboxes (all ticked by default, OR logic) to choose what shows. The time frame is Today / Tomorrow / Next 7 days (starting today) / Select a date, with no time-of-day picker. Events that have already ended are hidden
* **Checkboxes use GT's own category names (user, 2026-10-28):** students already know the names on GT's RSS feeds page, so the filter is Food plus the 10 feed names (`GT_CATEGORIES` in `map.html`, same as `FEEDS`), read from each event's `categories` field. GT's extra tags without a feed ("Performance", "Talk", "Free", ...) are left out. The empty Special event feed has no box since 2026-10-29; add it back when GT fixes it. Student sponsored keeps its box although its feed is broken, because events from other feeds carry that tag (13 on 2026-10-29). "Arts and Performance" is shown as "Arts & Performance" (`DISPLAY_NAMES`; `events.json` keeps GT's name). Of `our_categories`, the map now uses only `food`; social/professional/sports/academic/arts/other are no longer shown. This settles the earlier "keep Social?" question (dropped)
* The user has emailed GT about the missing/broken/empty feeds (2026-10-26). When GT replies, re-run the pipeline and check the counts per checkbox

## Milestone Checklists

Tick items as they're done (`[x]`). A milestone is finished when every item is ticked and its "Done when" is true; then write its `milestones/milestoneN_summary.txt` and move on. Order can change if the user decides so.

### Milestone 2: Events on a map (complete, 2026-10-24)
Done when: `map.html` shows the next 10 events as correctly placed pins with popups, lists every unpinnable event in the same time frame, and the location match rate is known.

- [x] RSS reader writes `events.json` (dedupe across feeds, upcoming only, sanity check)
- [x] `locate.py` matches locations to buildings and reports the match rate (~81% of in-person events)
- [x] `map.html`: pins grouped by building, popups, building dots colored by coordinate source
- [x] Panel listing online / unmatched / no-location events for the same time frame as the pins
- [x] Corrected the buildings flagged as wrong (2026-10-24)
- [x] Add the user's new locations from `building_loc.txt` to `gt_buildings.json` (2026-10-24; match rate now 86%)
- [x] Check the remaining `approximate` (red) buildings by eye on the map (2026-10-24; all 57 buildings now checked by the user)
- [x] Email GT about the feed problems and the building list (sent 2026-10-24; awaiting reply)
- [x] Screenshot of the map in the README (`docs/map_milestone2.png`)
- [x] Merge GT's duplicate postings (same name, start and location but different URLs, e.g. "Georgia Tech Volleyball vs. SMU" and "...-vs-smu-0")
- [x] Write `milestones/milestone2_summary.txt` as complete

### Milestone 3: Filters and categories (complete, 2026-10-28)
Done when: a user can pick a time frame and categories and see only those events, on the map and in the list. (Changed by the user on 2026-10-26: originally "pick a day and time", with pins colored by category.)

- [x] Time frame filter (Today / Tomorrow / Next 7 days / a date); pins and the unmapped panel both follow it (replaces "next 10 events"). Checked by the user 2026-10-28
- [x] Map GT's categories to ours (food, social, professional, sports, academic, arts) with keyword rules, several per event; food from the feed's Extras field, the name or the write-up (2026-10-26, `categorize.py`). On 2026-10-28 the user switched the checkboxes to GT's own names; only Food is still ours, the other rules stay in `categorize.py` unused for possible later use
- [x] Registration-required flag (e.g. from related links like "Register" / "RSVP"); measure how often the rule is wrong (2026-10-26: 89 of 219 flagged; hand check found 1 clearly wrong, 2 doubtful, ~3%; no misses found in the text of the unflagged events)
- [x] Category checkboxes (with counts) filter the pins and the list. Checked by the user 2026-10-28
- [x] Popups show categories (including food) and registration. Checked by the user 2026-10-28
- [x] Measure the unmatched locations again; decide rules vs. LLM (default: rules) (2026-10-26: 83% match rate, 18 unmatched, mostly facilities break rooms and far-off places; decision: rules, no LLM)
- [x] Write `milestones/milestone3_summary.txt` as complete

### Milestone 4: Automatic updates to Firebase
Done when: events in Firebase refresh on their own once a day, and a failed refresh sends an email.

- [x] Create the Firebase project (2026-10-29): project ID `gt-event-map`, added to the user's existing GCP project (the one with the Maps key), so it's on the Blaze plan. The user has a hard quota on Maps and expects Hosting to stay in the free tier
- [x] Decide the format (2026-10-29): static `events.json` + `data/gt_buildings.json` on Firebase Hosting (`https://gt-event-map.web.app/...`). Firestore only once there are user features (saved events, accounts) or many sources
- [x] GitHub Actions job (`.github/workflows/refresh-events.yml`; first successful manual run 2026-10-29, events visible at `https://gt-event-map.web.app/events.json`). It deploys as service account `github-deploy`, whose JSON key is the `FIREBASE_SERVICE_ACCOUNT_GT_EVENT_MAP` secret, with roles Firebase Hosting Admin + Service Usage Consumer (without the second, the deploy fails with 403 on `serviceusage.services.get`). The job runs `gt_calendar_rss.py` + `locate.py` + `categorize.py` on a schedule and publishes the result to Firebase (the sanity check makes a broken run fail visibly; GitHub emails on failure). Firebase credentials go in GitHub Secrets, never in the repo
- [x] GitHub's failure emails are on (GitHub → Settings → Notifications → Actions; done by the user 2026-10-29)
- [ ] Confirm a scheduled (not manual) run succeeds
- Dropped (user, 2026-10-29): hosting `map.html` as a public web version. The phone app is the product; `map.html` stays a local prototype

### Milestone 5: Mobile app (Expo)
Done when: the app runs on the user's Android phone and iPhone through Expo Go and does what `map.html` does, with data from Firebase.

- [ ] Set up the Expo project (Node.js, Expo CLI; Android Studio emulator on the laptop; Expo Go on both phones)
- [ ] Map of campus with event pins grouped by building, and event details on tap
- [ ] Time frame (Today / Tomorrow / Next 7 days / a date) and category checkboxes, as in `map.html`
- [ ] "Not on the map" list (online, unmatched, off campus, no location)
- [ ] Loads events from Firebase; works sensibly offline or when loading fails
- [ ] Checked by the user on both phones

### Milestone 6: Publish on Google Play
Done when: the app is live on Google Play.

- [ ] Google Play developer account ($25 once)
- [ ] Production Android build via EAS, with its own Google Maps Android key restricted to the app
- [ ] Privacy policy, store listing, screenshots, app icon
- [ ] Closed test if Google still requires one for new personal accounts (was 12 testers for 14 days; check the current rule)
- [ ] Live store link in the README

### Milestone 7: Publish on the App Store
Done when: the app is live on the Apple App Store.

- [ ] Apple Developer account ($99/year)
- [ ] iOS build via EAS (no Mac needed); map provider decided (Apple Maps by default, or Google Maps with an iOS key)
- [ ] TestFlight test on the user's iPhone, then App Store review

### Milestone 8: More sources
Done when: events from at least one more source appear alongside the calendar's, without duplicates.

- [ ] Engage (gatech.campuslabs.com): check for an official feed/API and its terms first, as with the calendar
- [ ] GT Athletics (ramblinwreck.com)
- [ ] Remove duplicates across sources (same event posted in two places)
- [ ] LLM only for sources plain parsing can't handle

## Repository Notes

* Git repo on branch `main`, pushed to GitHub at `git@github.com:vix-bram/event-aggregator-app.git` (account `vix-bram`, SSH auth)
* `.gitignore` excludes `venv/`, `events_output.txt` (regenerated by running the scraper), `.env` files (API keys go here — never commit them), and `.claude/settings.local.json`

