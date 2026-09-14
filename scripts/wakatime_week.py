#!/usr/bin/env python3
"""Fill the WakaTime placeholders in a rendered README.

lowlighter/metrics reads WakaTime's /stats/{range} endpoint, which is a cached
daily rollup: it always ends at the last complete day (is_including_today is
false) and its total_seconds silently excludes time logged under the "Other"
language. For an account whose time comes mostly from AI-coding plugins that is
almost everything, so the README showed 0h 17m instead of 4h 29m.

/summaries?range=last_7_days is computed on the fly, includes today, and is the
endpoint the WakaTime dashboard itself uses, so the numbers below match what the
dashboard shows.
"""

import json
import os
import sys
import urllib.request
from base64 import b64encode

API = "https://wakatime.com/api/v1/users/current/summaries?range=last_7_days"

# Languages that describe config/prose rather than what was actually built.
# "Other" is WakaTime's bucket for heartbeats with no detected language.
NOT_A_LANGUAGE = {
    "other", "json", "yaml", "toml", "ini", "markdown", "text",
    "makefile", "gitignore", "git config", "csv", "log", "image",
}


def fetch(token):
    auth = b64encode(token.encode()).decode()
    req = urllib.request.Request(API, headers={"Authorization": f"Basic {auth}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def total_text(payload):
    seconds = int(payload["cumulative_total"]["seconds"])
    # Floor the minutes, the way WakaTime's own "4 hrs 29 mins" text does.
    return f"{seconds // 3600}h {seconds % 3600 // 60}m"


def top_language(payload):
    totals = {}
    for day in payload["data"]:
        for lang in day.get("languages", []):
            totals[lang["name"]] = totals.get(lang["name"], 0) + lang["total_seconds"]
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])
    for name, _ in ranked:
        if name.lower() not in NOT_A_LANGUAGE:
            return name.lower()
    # Nothing but config/prose this week; fall back to the busiest bucket.
    return ranked[0][0].lower() if ranked else "nothing"


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: wakatime_week.py <readme-path>")
    path = sys.argv[1]

    token = os.environ.get("WAKATIME_API_KEY", "").strip()
    if not token:
        sys.exit("WAKATIME_API_KEY is not set")

    payload = fetch(token)
    total, language = total_text(payload), top_language(payload)
    print(f"wakatime last 7 days: {total}, top language: {language}")

    with open(path, encoding="utf-8") as handle:
        readme = handle.read()

    for placeholder, value in (("__WAKA_TOTAL__", total), ("__WAKA_LANG__", language)):
        if placeholder not in readme:
            sys.exit(f"{placeholder} is missing from {path}; template out of sync")
        readme = readme.replace(placeholder, value)

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(readme)


if __name__ == "__main__":
    main()
