#!/usr/bin/env python3
"""
Phase 4-6 der Punkte-Auswertung: normalisiert Teilnehmernamen aus
thread_archive/point_events.jsonl und aggregiert die Punkte pro Teilnehmer und
Jahr (plus Gesamtsumme und Sonderpunkte-Anteil) in eine CSV-Tabelle.

Beispiel:
    python3 build_table.py
    python3 build_table.py --output punkte_tabelle.csv
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

# Bekannte Namensvarianten, die nicht ueber reinen Gross-/Kleinschreibungs-Abgleich
# gegen die Autorenliste aufgeloest werden koennen. Bei Bedarf ergaenzen, wenn beim
# Skalieren auf den vollen Thread neue Spitznamen/Varianten auftauchen.
ALIAS_MAP = {
    "wanderbär sido": "Wanderbär",
    "crazyhorse": "Crazy Horse",
    "crazy": "Crazy Horse",
    "donuvo": "Don Uvo",
    "dürens": "Düren",
    "fritzelore": "Fritzlore",
    "jochen": "jochen02",
    "johanna": "Johanna68",
    "lucky boy": "Luckyboy",
    "meerschatz": "Meerkatze",
    "mehrkatze": "Meerkatze",
    "merrkatze": "Meerkatze",
    "el turisto": "el turista",
    "che": "Che Guevara",
    "mago89": "Ex mago89",
    # Post 51303: Autor raeumt selbst ein "geaendert wegen Namensverwirrung.
    # Entschuldige Hartmut!" - "Helmut" war ein Verwechslungsfehler, keine eigene Person.
    "helmut": "hartmut",
    "jason": "Jason",
}


def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def build_canonical_lookup(posts):
    authors = sorted(set(p["author"] for p in posts if p.get("author")))
    return {a.lower(): a for a in authors}


def normalize_name(name: str, canonical_by_lower: dict):
    key = name.strip().lower()
    if key in ALIAS_MAP:
        return ALIAS_MAP[key], True
    if key in canonical_by_lower:
        return canonical_by_lower[key], True
    return name.strip(), False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", default="thread_archive/point_events.jsonl")
    parser.add_argument("--posts", default="thread_archive/posts.jsonl")
    parser.add_argument("--output", default="thread_archive/punkte_tabelle.csv")
    args = parser.parse_args()

    events = load_jsonl(Path(args.events))
    posts = load_jsonl(Path(args.posts))
    canonical_by_lower = build_canonical_lookup(posts)

    totals = defaultdict(lambda: defaultdict(int))
    sonder = defaultdict(lambda: defaultdict(int))
    years = set()
    unmapped = set()

    for e in events:
        name, mapped = normalize_name(e["empfaenger"], canonical_by_lower)
        if not mapped:
            unmapped.add(e["empfaenger"])
        year = e.get("year") or "unbekannt"
        years.add(year)
        totals[name][year] += e["gesamtpunkte"]
        sonder[name][year] += e.get("davon_sonderpunkte", 0)

    years = sorted(years)
    participants = sorted(
        totals.keys(),
        key=lambda n: -sum(totals[n].values()),
    )

    out_path = Path(args.output)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        header = ["Teilnehmer"] + years + ["Gesamt", "davon Sonderpunkte"]
        writer.writerow(header)
        for name in participants:
            row_total = sum(totals[name].values())
            row_sonder = sum(sonder[name].values())
            row = [name] + [totals[name].get(y, 0) for y in years] + [row_total, row_sonder]
            writer.writerow(row)

    print(f"Tabelle geschrieben nach {out_path.resolve()}")
    print(f"{len(participants)} Teilnehmer, Jahre: {years}")
    if unmapped:
        print(f"\nACHTUNG - nicht eindeutig zugeordnete Namen (bitte pruefen/ALIAS_MAP ergaenzen):")
        for n in sorted(unmapped):
            print(f"  - {n!r}")

    print("\nVorschau:")
    with out_path.open(encoding="utf-8") as f:
        for line in f:
            print(" ", line.rstrip())


if __name__ == "__main__":
    main()
