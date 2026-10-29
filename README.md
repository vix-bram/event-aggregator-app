## GT Event Map: Finding Events on Georgia Tech's Campus

A map of what's happening on Georgia Tech's campus, built from the official GT campus calendar feeds.

<!-- Add a live demo link here once the app is deployed, e.g.
**[Live demo](https://your-app.vercel.app)** -->

![GT Event Map: events for the next 7 days pinned on the Georgia Tech campus map, with category checkboxes in a gold bar above the map and a side panel on the left listing the online and unlocated events with their times, locations and tags](docs/map_milestone3.png)

### Why I'm building this

When I was a Tech student, I missed out on many events because there were too many places to look for them, and I couldn't see the events on a map or filter them by what I cared about. This app pulls event information into one place and shows it on a map of campus, so students can find events more easily and be more involved in campus life.

It's being built for Georgia Tech first. The goal is to eventually expand to college campuses across the country.

### Features

**Working now**
* Reads upcoming events from the official [GT campus calendar RSS feeds](https://calendar.gatech.edu/rss-feeds), combining events that appear in more than one category feed
* Matches free-text locations ("Room 357, Clough Undergraduate Learning Commons") to campus buildings with known coordinates, and recognizes online/TBD events that can't be pinned - display these in a side panel
* Shows events as pins on a Google Map of campus, one pin per building, with a popup listing each building's events
* Filter by time frame: Today, Tomorrow, Next 7 days, or a specific date
* Filter by category with checkboxes, using the same category names as GT's calendar (Arts and Performance, Career/Professional development, Sports/Athletics, ...), plus a Food filter
* Each event card shows its time range, location, categories, and whether it has food or needs registration
* Events that can't be pinned (online, no location, or a place that isn't on the map yet) are listed in a side panel with their location text, following the same filters as the pins, so no event is hidden just because it has no pin

**Planned**
* Refresh events automatically on a schedule (GitHub Actions)
* Deploy publicly on Vercel
* More event sources (student organizations on Engage, athletics, department pages)
* Store events in Firebase, once there are user features like saved events

### Tech stack

* **Data collection:** Python, `requests`, BeautifulSoup, ElementTree (RSS)
* **Map:** HTML/JavaScript, Google Maps JavaScript API
* **Planned:** Firebase (Firestore), GitHub Actions for scheduled updates, Vercel hosting, React

### Technical decisions

* **Official feeds instead of scraping.** The first version pulled events out of the calendar's web page. I switched to GT's published RSS feeds because that's the channel GT offers for reusing its event data. Checking the feeds against the page showed they covered only about 40% of upcoming events: one feed is broken, one is empty, one category's link points to the wrong feed (I found the right one by its ID), and events with no category aren't in any feed. I documented these issues to report to GT rather than quietly working around them. The reader identifies itself in its User-Agent and pauses between requests.
* **No LLM where plain code works.** The feeds are already structured (labeled sections for time, location, fee and extras), so plain Python parsing gives exact results. An LLM would add cost, latency and randomness without improving the data. I'll only consider one for messy sources, after measuring what simple rules miss.
* **Location matching with measurable results.** Event locations are free text written by whoever posted the event, often down to the room. `locate.py` matches whole-word building keywords (so "crc" doesn't match inside another word) and labels every event as matched, unmatched, online or no location. It prints the match rate (currently about 73% of in-person events) and the most common unmatched locations, which is my to-do list for improving it. I don't guess coordinates for places I don't know; those events go in the side panel with their location text, so students can still find them.
* **GT's category names instead of my own.** I first sorted events into my own categories (social, professional, sports, ...) with keyword rules. I switched the filters to the names GT's calendar already uses, because students who know the calendar would be confused by a second set of names. Food is the one category I added, since GT doesn't have one.
* **Food and registration from simple rules.** `categorize.py` marks an event as having food from the calendar's own "Free food" tag, food words in the name, or phrases like "lunch will be served" in the description. I call it "Food" rather than "Free food", since whether it's free (or only for people who registered) is for the student to check. It marks "Registration required" when the links, location, fee or description mention registering, RSVPing, signing up or tickets. A hand check found about 3% of the registration flags wrong, which is low enough that an LLM isn't worth it.
* **Fail loudly instead of silently.** If a run finds no events, or most events come back without a name or location (a sign the feed format changed), the reader stops with an error and keeps the previous `events.json`, so the map never quietly goes blank.
* **One pin per building.** Events in the same building are grouped into one numbered pin, instead of several pins stacked exactly on top of each other.

### Getting Started

You need Python 3 and a Google Maps JavaScript API key. Run these commands from the project folder (on Mac/Linux, replace `venv/Scripts/` with `venv/bin/`).

1. Create a virtual environment and install the dependencies:
   ```bash
   python -m venv venv
   venv/Scripts/pip install -r requirements.txt
   ```

2. If the environment is not activated, activate it:
   ```bash
   source venv/Scripts/activate
   ```

3. Add your API key: copy `config.example.js` to `config.js` and paste your key into it. `config.js` is gitignored, so your key stays off GitHub.
   ```bash
   cp config.example.js config.js
   ```
4. Download the latest events, match each one to a campus building, and label whether it has food or needs registration. All three scripts write to `events.json`, so run them in this order, and run all three again whenever you want fresh events:
   ```bash
   venv/Scripts/python scraper/gt_calendar_rss.py
   venv/Scripts/python locate.py
   venv/Scripts/python categorize.py
   ```
5. Start a local server and open http://localhost:8000/map.html in your browser:
   ```bash
   venv/Scripts/python -m http.server 8000
   ```
   Opening `map.html` by double-clicking it won't work, because browsers block pages opened from disk from loading `events.json`.

### Acknowledgments
* Built with coding assistance and architectural guidance from Claude by Anthropic.
