# Campus Event Aggregator — Project Overview

## The Problem

Campus events at Georgia Tech are scattered across dozens of sources: department websites, student organization pages, athletics calendars, and more. Students miss events simply because the information is fragmented and hard to track.

## The Goal

Build a web app that automatically scrapes publicly available Georgia Tech webpages for event information, parses that information using an LLM API, stores it in a database, and displays events as color-coded pins on an interactive Google Maps interface of the GT campus.

## Core Features

* **Automated scraping**: A scheduled job visits a list of known GT event pages on a recurring basis (e.g. every 6 hours) and extracts raw text
* **LLM parsing**: The scraped text is sent to the Google Gemini API, which extracts structured event data (name, date, time, location, description, category)
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
* **LLM parsing**: Google Gemini API (free tier to start)
* **Database**: Firebase (Firestore)
* **Frontend**: React with Google Maps JavaScript API
* **Hosting**: Vercel
* **Scheduling**: GitHub Actions or Google Cloud Scheduler

## Target Scrape Sources (Georgia Tech)

* GT Campus Calendar: https://calendar.gatech.edu
* GT Student Engagement (Corq/Engage): https://gatech.campuslabs.com/engage/events
* GT Athletics: https://ramblinwreck.com
* Individual department event pages (to be expanded over time)

## Build Approach

* The developer is new to software development, so code should be well-commented and easy to understand
* Start simple: get one scraper working, then add LLM parsing, then the database, then the frontend
* Prioritize a working prototype over a polished product
* Each component should be buildable and testable independently before integrating

## Current Status

Starting from scratch. The first milestone is a working Python scraper for one GT webpage (calendar.gatech.edu) that prints structured event data to the terminal.

