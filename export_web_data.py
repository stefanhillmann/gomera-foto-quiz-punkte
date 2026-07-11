#!/usr/bin/env python3
"""
Exportiert die Punkte-Daten als statische JSON-Datei fuer das Web-Tool
(docs/data/data.json), das per GitHub Pages gehostet wird.

Enthaelt NUR strukturierte Fakten (Namen, Zahlen, Daten, Links auf den
Original-Forenpost) - niemals Forentext, siehe README/Plan.

Beispiel:
    python3 export_web_data.py
    python3 export_web_data.py --output docs/data/data.json
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from build_table import build_canonical_lookup, normalize_name
from download_thread import BASE_URL


def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def permalink(post_id: str) -> str:
    return f"{BASE_URL}&p={post_id}&viewfull=1#post{post_id}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", default="thread_archive/point_events.jsonl")
    parser.add_argument("--posts", default="thread_archive/posts.jsonl")
    parser.add_argument("--meta", default="thread_archive/meta.json")
    parser.add_argument("--output", default="docs/data/data.json")
    args = parser.parse_args()

    raw_events = load_jsonl(Path(args.events))
    posts = load_jsonl(Path(args.posts))
    meta_in = json.loads(Path(args.meta).read_text(encoding="utf-8"))
    canonical_by_lower = build_canonical_lookup(posts)

    unmapped = set()
    events_out = []
    totals = defaultdict(lambda: defaultdict(int))
    sonder = defaultdict(lambda: defaultdict(int))
    wins = defaultdict(lambda: defaultdict(int))
    years = set()

    for e in raw_events:
        empfaenger, mapped_e = normalize_name(e["empfaenger"], canonical_by_lower)
        melder, mapped_m = normalize_name(e["melder"], canonical_by_lower)
        if not mapped_e:
            unmapped.add(e["empfaenger"])
        if not mapped_m:
            unmapped.add(e["melder"])

        year = e.get("year") or "unbekannt"
        years.add(year)
        totals[empfaenger][year] += e["gesamtpunkte"]
        sonder[empfaenger][year] += e.get("davon_sonderpunkte", 0)
        wins[empfaenger][year] += 1

        events_out.append({
            "post_id": e["post_id"],
            "page": e["page"],
            "date": e["date"],
            "year": year,
            "melder": melder,
            "empfaenger": empfaenger,
            "gesamtpunkte": e["gesamtpunkte"],
            "davon_sonderpunkte": e.get("davon_sonderpunkte", 0),
            "permalink": permalink(e["post_id"]),
        })

    years = sorted(years)
    participants = []
    for name in totals:
        total_points = sum(totals[name].values())
        total_sonder = sum(sonder[name].values())
        total_wins = sum(wins[name].values())
        year_map = {
            y: {
                "points": totals[name].get(y, 0),
                "sonderpunkte": sonder[name].get(y, 0),
                "wins": wins[name].get(y, 0),
            }
            for y in years
        }
        participants.append({
            "name": name,
            "total_points": total_points,
            "total_sonderpunkte": total_sonder,
            "total_wins": total_wins,
            "years": year_map,
        })

    participants.sort(key=lambda p: (-p["total_points"], p["name"]))

    data = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "thread_url": meta_in.get("thread_url"),
            "thread_title": meta_in.get("title"),
            "years": years,
            "event_count": len(events_out),
            "participant_count": len(participants),
        },
        "participants": participants,
        "events": events_out,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Geschrieben nach {out_path.resolve()}")
    print(f"{len(participants)} Teilnehmer, {len(events_out)} Ereignisse, Jahre: {years}")
    if unmapped:
        print("\nACHTUNG - nicht eindeutig zugeordnete Namen:")
        for n in sorted(unmapped):
            print(f"  - {n!r}")


if __name__ == "__main__":
    main()
