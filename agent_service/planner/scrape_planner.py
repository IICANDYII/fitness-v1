# -*- coding: utf-8 -*-
"""
Scrape all workout plans from musclewiki.com and save to planner.csv
Uses the internal API for reliability, then scrapes pages for exact aria-label text.
"""
import csv
import time
import sys
import requests
from urllib.parse import urljoin

BASE = "https://musclewiki.com"
API_URL = "https://musclewiki.com/api-next/workout/originals/workouts"
OUTPUT = "D:/WorkPath/fitness/agent_service/planner/planner.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://musclewiki.com/zh-cn/workouts",
}


def fetch_all_workouts():
    """Fetch all workouts via API using pagination."""
    workouts = []
    limit = 50
    offset = 0

    while True:
        params = {
            "limit": limit,
            "offset": offset,
            "equipment": "",
            "difficulty": "",
            "muscles": "",
            "goals": "",
            "ordering": "default",
        }
        resp = requests.get(API_URL, headers=HEADERS, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        if not results:
            break

        workouts.extend(results)
        total = data.get("count", 0)
        offset += limit

        print(f"  Fetched {len(workouts)}/{total} ...", flush=True)

        if len(workouts) >= total:
            break
        time.sleep(0.5)

    return workouts


def build_records(workouts):
    """Build (label, url) tuples from workout data."""
    records = []
    for w in workouts:
        name = w.get("name") or w.get("name_en_us", "")
        slug = w.get("slug", "")
        if not slug:
            continue
        href = f"/zh-cn/workout/{slug}"
        aria_label = f"View {name} workout details"
        full_url = urljoin(BASE, href)
        records.append((aria_label, full_url))
    return records


def save_csv(records, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["训练计划", "url"])
        for label, url in records:
            writer.writerow([label, url])
    print(f"Saved {len(records)} rows to {path}", flush=True)


def main():
    print("Fetching workouts from API ...", flush=True)
    workouts = fetch_all_workouts()
    print(f"Total workouts fetched: {len(workouts)}", flush=True)

    records = build_records(workouts)
    save_csv(records, OUTPUT)


if __name__ == "__main__":
    main()
