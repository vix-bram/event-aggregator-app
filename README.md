## Application for Finding Events on College Campus (Georgia Tech): *app name*

In this project, I am building a web application to check what events are happening on Georgia Tech's campus. The purpose of
the app is to help students find events more easily be more involved in campus social life. 
How the app works is that it scrapes event information from several web pages and displays them neatly on a map. It allows for
filtering based on the type of event, time of event, whether one needs to sign up, whether there's food, etc. When I was a Tech student, I missed out on many events because I felt like there were too many places to look for them. Additionally, I could not see the events on a map and filter based on several criteria.

Initially, the app is being built for finding events on Georgia Tech's campus. The goal is to eventually expand the app to several college campuses across the nation and make finding events easier for students!

### Getting Started

You need Python 3 and a Google Maps JavaScript API key. Run these commands from the project folder (on Mac/Linux, replace `venv/Scripts/` with `venv/bin/`).

1. Create a virtual environment and install the dependencies:
   ```bash
   python -m venv venv
   venv/Scripts/pip install -r requirements.txt
   ```
2. Add your API key: copy `config.example.js` to `config.js` and paste your key into it. `config.js` is gitignored, so your key stays off GitHub.
   ```bash
   cp config.example.js config.js
   ```
3. Scrape the GT calendar and match each event to a campus building. Both scripts write to `events.json`, so run them in this order, and run both again whenever you want fresh events:
   ```bash
   venv/Scripts/python scraper/gt_calendar_scraper.py
   venv/Scripts/python locate.py
   ```
4. Start a local server and open http://localhost:8000/map.html in your browser:
   ```bash
   venv/Scripts/python -m http.server 8000
   ```
   Opening `map.html` by double-clicking it won't work, because browsers block pages opened from disk from loading `events.json`.

### Acknowledgments
* Built with coding assistance and architectural guidance from Claude by Anthropic.
