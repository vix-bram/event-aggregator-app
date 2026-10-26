"""
Category and registration rules — Milestone 3.

What this script does, step by step:
1. Reads events.json (after scraper/gt_calendar_rss.py and locate.py).
2. Gives every event all of our categories that fit (an event can have
   several, e.g. a concert with food is both "arts" and "food"):
     food, social, professional, sports, academic, arts, other
   using plain keyword rules:
     a. keywords in the event's name ("concert" -> arts, "info session"
        -> academic). GT's own tags are often vague (most "Other/
        Miscellaneous" events are really info sessions, deadlines or
        holidays), so the name catches what they miss.
     b. GT's own categories ("Sports/Athletics" -> sports). The broad ones
        ("Training/Workshop", "Student sponsored") count only when nothing
        else matched.
     c. food: GT's "Free food" tag in Extras, a food word in the name
        ("Lunch & Learn"), or a phrase like "lunch will be served" in the
        write-up. We say "food", not "free food": whether it's really free
        (or only for people who registered) is for the student to check on
        the event page.
     d. no topic matched -> "other" (holidays, closures, ...). "food" isn't
        a topic, so an event with only food is "food" and "other".
3. Sets registration_required: true if a related link, the location, the
   fee or the write-up talks about registering, RSVPing, signing up or
   tickets ("No registration required" doesn't count).
4. Each rule records why it fired (category_reasons, registration_reason),
   so a wrong label can be traced back to its rule.
5. Saves the events back to events.json and prints how many events each
   rule labeled, so we can see what the rules miss.

Run it after the other two scripts, e.g. (in bash):
    venv/Scripts/python scraper/gt_calendar_rss.py
    venv/Scripts/python locate.py
    venv/Scripts/python categorize.py
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

from locate import contains_keyword, normalize

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent
EVENTS_PATH = PROJECT_ROOT / "events.json"

# Listed in the order map.html shows them.
CATEGORIES = ["food", "social", "professional", "sports", "academic", "arts", "other"]

# Step 2a: whole-word keywords in the event name. Every category with a
# matching keyword is given, so "Halloween Holla 5K" is sports and social.
NAME_RULES = [
    ("sports", [
        "vs", "5k", "10k", "football", "basketball", "baseball",
        "softball", "volleyball", "soccer", "tennis", "swimming", "golf",
        "intramural", "yoga", "fitness",
    ]),
    ("arts", [
        "concert", "recital", "exhibit", "exhibition", "gallery", "film",
        "screening", "theatre", "theater", "dramatech", "dance", "orchestra",
        "choir", "ensemble", "museum", "poetry", "art show",
    ]),
    ("professional", [
        "career", "networking", "resume", "résumé", "interview", "internship",
        "employer", "employers", "employment", "job fair", "recruiting",
        "leading at tech", "professional development", "training",
    ]),
    ("academic", [
        "seminar", "lecture", "colloquium", "symposium", "conference",
        "info session", "information session", "thesis", "dissertation",
        "defense", "deadline", "commencement", "class days", "no classes",
        "fossil friday",
    ]),
    ("social", [
        "party", "social", "mixer", "festival", "gradfest", "celebration",
        "halloween", "trick or treating", "tailgate", "homecoming",
        "game night", "trivia", "recess", "pop-up", "coffeehouse",
        "plant library",
    ]),
]

# Step 2b: GT's categories. GT categories not listed here
# ("Other/Miscellaneous", "Free", "Special event") tell us nothing.
GT_CATEGORY_RULES = [
    ("sports", ["Sports/Athletics"]),
    ("arts", ["Arts and Performance", "Performance", "Exhibit"]),
    ("professional", ["Career/Professional development", "Industry"]),
    ("academic", ["Seminar/Lecture/Colloquium", "Conference/Symposium", "Talk"]),
]
# GT categories too broad to add on top of a clear topic (a student-run
# finance workshop isn't "social"), so they're only used when nothing above
# matched.
GT_FALLBACK_RULES = [
    # Most of GT's workshops are staff or skills training (PACE, safety).
    ("professional", ["Training/Workshop", "Workshop"]),
    ("social", ["Student sponsored"]),
]

# Step 2c: food words in the event name ("Lunch & Learn", "Pizza Night").
FOOD_NAME_KEYWORDS = [
    "food", "pizza", "lunch", "breakfast", "brunch", "dinner", "snacks",
    "refreshments", "bbq", "barbecue", "cookout", "potluck",
]

# Step 2c: food mentioned in the write-up, e.g. "free pizza" or "A light
# lunch will be served". Food words alone aren't enough ("food
# insecurity", "food drive"), so the phrase must say it's free or
# served/provided.
FOOD_WORDS = r"(food|pizza|lunch|breakfast|dinner|snacks?|refreshments|light bites|drinks|coffee)"
FOOD_PATTERNS = [
    re.compile(rf"\b(free|complimentary)\s+{FOOD_WORDS}\b", re.IGNORECASE),
    re.compile(rf"\b{FOOD_WORDS}\b[^.]{{0,40}}\b(will be|are|is)\s+(served|provided)\b", re.IGNORECASE),
]

# Step 3: registration. "Registrar" (the office) is a different word, so the
# \b on both sides keeps it from matching.
REGISTRATION_PATTERN = re.compile(
    r"\b(register|registration|registering|rsvp|sign[ -]?up|tickets?)\b", re.IGNORECASE
)
NO_REGISTRATION_PATTERN = re.compile(
    r"\bno (registration|rsvp|tickets?)\b|\b(registration|rsvp|tickets?) (is )?not required\b",
    re.IGNORECASE,
)
# Link addresses that are registration pages even when the link text is
# just "Learn more".
REGISTRATION_URL_PATTERN = re.compile(r"register|registration|rsvp|signup|sign-up|eventbrite|tickets?", re.IGNORECASE)


def food_reason(event: dict) -> str | None:
    """Why we think the event has food, or None if we see no sign of it."""
    if "Free food" in event["extras"]:
        return "Extras: Free food"
    name = normalize(event["name"])
    for keyword in FOOD_NAME_KEYWORDS:
        if contains_keyword(name, keyword):
            return f"name: {keyword}"
    for pattern in FOOD_PATTERNS:
        match = pattern.search(event.get("details", "") or event["description"])
        if match:
            return f"text: {match.group(0)}"
    return None


def pick_categories(event: dict) -> dict[str, str]:
    """
    Return {category: reason} for every category that fits (step 2), in
    CATEGORIES order. The reason is the first rule that gave it.
    """
    reasons: dict[str, str] = {}
    name = normalize(event["name"])
    for category, keywords in NAME_RULES:
        for keyword in keywords:
            if contains_keyword(name, keyword):
                reasons.setdefault(category, f"name: {keyword}")
                break
    for category, gt_categories in GT_CATEGORY_RULES:
        for gt_category in gt_categories:
            if gt_category in event["categories"]:
                reasons.setdefault(category, f"GT: {gt_category}")
                break
    for category, gt_categories in GT_FALLBACK_RULES:
        if reasons:
            break
        for gt_category in gt_categories:
            if gt_category in event["categories"]:
                reasons[category] = f"GT: {gt_category}"
                break
    if not reasons:
        reasons["other"] = "no rule matched"
    food = food_reason(event)
    if food:
        reasons["food"] = food
    return {c: reasons[c] for c in CATEGORIES if c in reasons}


def registration_reason(event: dict) -> str | None:
    """Why the event needs registration, or None if we see no sign of it."""
    for link in event["related_links"]:
        if REGISTRATION_PATTERN.search(link["text"]):
            return f"link: {link['text']}"
        if REGISTRATION_URL_PATTERN.search(link["url"]):
            return f"link address: {link['url']}"
    fields = [
        ("location", event["location"]),
        ("fee", event["fee"]),
        ("text", event.get("details", "") or event["description"]),
    ]
    for field, text in fields:
        if NO_REGISTRATION_PATTERN.search(text):
            continue
        match = REGISTRATION_PATTERN.search(text)
        if match:
            return f"{field}: {match.group(0)}"
    return None


def categorize_event(event: dict) -> None:
    """Add our categories and the registration flag to one event (in place)."""
    reasons = pick_categories(event)
    event["our_categories"] = list(reasons)
    event["category_reasons"] = reasons
    event["registration_reason"] = registration_reason(event)
    event["registration_required"] = event["registration_reason"] is not None


def print_summary(events: list[dict]) -> None:
    total = len(events)
    categories = Counter(c for e in events for c in e["our_categories"])
    print(f"Categorized {total} events (an event can count in several categories):")
    for category in CATEGORIES:
        count = categories[category]
        print(f"  {category:<13} {count:>4}  ({count / total:.0%})")
    topics = Counter(len([c for c in e["our_categories"] if c != "food"]) for e in events)
    print("Topics per event: " + ", ".join(f"{n} topic(s): {topics[n]}" for n in sorted(topics)))

    # Where the labels came from: the name rules, GT's tags, or nothing.
    sources = Counter(reason.split(":")[0]
                      for e in events
                      for category, reason in e["category_reasons"].items()
                      if category != "food")
    print("Topic labels from: " + ", ".join(f"{s} {n}" for s, n in sources.most_common()))

    others = Counter(e["name"] for e in events if "other" in e["our_categories"])
    if others:
        print("\nEvents with no topic (add name keywords for these if they deserve one):")
        for name, count in others.most_common(20):
            print(f"  {count:>3}  {name}")

    food = Counter(e["category_reasons"]["food"].split(":")[0]
                   for e in events if "food" in e["our_categories"])
    print(f"\nFood: {sum(food.values())} events ({food['Extras']} tagged by GT, "
          f"{food['name']} from the name, {food['text']} from the write-up)")
    for e in events:
        reason = e["category_reasons"].get("food", "")
        if reason and not reason.startswith("Extras"):
            print(f"  {e['name'][:60]:<60}  <- {reason}")

    registration = Counter(e["registration_reason"].split(":")[0]
                           for e in events if e["registration_required"])
    print(f"\nRegistration required: {sum(registration.values())} events ("
          + ", ".join(f"{s} {n}" for s, n in registration.most_common()) + ")")


def main() -> None:
    events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    for event in events:
        categorize_event(event)

    with open(EVENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

    print_summary(events)
    print(f"\nSaved categorized events to {EVENTS_PATH}")


if __name__ == "__main__":
    main()
