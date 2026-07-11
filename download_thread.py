#!/usr/bin/env python3
"""
Lädt alle Seiten eines vBulletin-Threads (gomeraforum.de) herunter und
speichert ausschließlich die textuellen Informationen (Autor, Datum,
Beitragsnummer, Nachrichtentext) lokal ab. Bilder werden nicht heruntergeladen.

Nutzung wurde vom Forenbetreiber genehmigt.

Beispiel:
    python3 download_thread.py
    python3 download_thread.py --start-page 50 --end-page 60
    python3 download_thread.py --delay 3
"""

import argparse
import json
import random
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

THREAD_ID = "1754"
THREAD_SLUG = "Das-La-Gomera-Foto-Quiz"
BASE_URL = f"https://www.gomeraforum.de/showthread.php?{THREAD_ID}-{THREAD_SLUG}"

HEADERS = {
    # Eigener, ehrlicher User-Agent statt Spoofing eines Browsers -
    # der Betreiber hat das Scraping genehmigt.
    "User-Agent": "GomeraForumThreadArchiver/1.0 (persoenliche Textanalyse, "
                  "mit Erlaubnis des Betreibers; Kontakt: myrtel)"
}


def page_url(page: int) -> str:
    if page <= 1:
        return BASE_URL
    return f"{BASE_URL}/page{page}"


def fetch(session: requests.Session, url: str, retries: int = 3) -> str:
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except requests.RequestException as e:
            last_err = e
            wait = 5 * attempt
            print(f"  Fehler beim Abruf ({attempt}/{retries}): {e} - warte {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"Konnte {url} nicht laden: {last_err}")


def detect_total_pages(html: str) -> int:
    m = re.search(r"Seite\s+\d+\s+von\s+(\d+)", html)
    if m:
        return int(m.group(1))
    return 1


def normalize_date(date_text):
    """Ersetzt relative Datumsangaben ("Heute", "Gestern"), die vBulletin fuer sehr
    aktuelle Beitraege statt eines festen Datums anzeigt, durch ein echtes Datum
    im gleichen Format (TT.MM.JJJJ, HH:MM)."""
    if not date_text:
        return date_text
    m = re.match(r"(Heute|Gestern)\s*,?\s*(\d{1,2}:\d{2})", date_text, re.IGNORECASE)
    if not m:
        return date_text
    word, time_part = m.groups()
    day = datetime.now() if word.lower() == "heute" else datetime.now() - timedelta(days=1)
    return f"{day.strftime('%d.%m.%Y')}, {time_part}"


def extract_quote_info(tag):
    """Liefert (quoted_author, quoted_post_id) des ersten (aeussersten) Zitatblocks, falls vorhanden."""
    quote_div = tag.find("div", class_="bbcode_postedby")
    if quote_div is None:
        return None, None
    strong = quote_div.find("strong")
    quoted_author = strong.get_text(strip=True) if strong else None
    quoted_post_id = None
    link = quote_div.find("a", href=True)
    if link:
        m = re.search(r"[?&]p=(\d+)", link["href"])
        if m:
            quoted_post_id = m.group(1)
    return quoted_author, quoted_post_id


def clean_message_html(msg_tag) -> str:
    """Entfernt Bilder/Anhaenge/zitierte Fremdtexte und wandelt <br> in Zeilenumbrueche,
    bevor der eigentliche (neue) Text extrahiert wird."""
    tag = msg_tag.__copy__()
    for img in tag.find_all("img"):
        img.decompose()
    for a in tag.find_all("a", attrs={"class": "attachedimages"}):
        a.decompose()
    # Zitatbloecke (fremder, bereits an anderer Stelle gespeicherter Text) entfernen,
    # damit nur der neu geschriebene Anteil im Text landet.
    for quote in tag.find_all("div", class_="bbcode_container"):
        quote.decompose()
    for br in tag.find_all("br"):
        br.replace_with("\n")
    text = tag.get_text("", strip=False)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_posts(html: str, page_num: int):
    soup = BeautifulSoup(html, "html.parser")
    posts = []
    seen_ids = set()

    for li in soup.select('li[id^="post_"]'):
        post_id_attr = li.get("id", "")
        m = re.match(r"post_(\d+)$", post_id_attr)
        if not m:
            continue
        post_id = m.group(1)
        if post_id in seen_ids:
            continue

        msg_tag = li.select_one(f'div[id="post_message_{post_id}"]')
        if msg_tag is None:
            continue
        seen_ids.add(post_id)

        author_tag = li.select_one("a.username, span.username")
        author = author_tag.get_text(strip=True) if author_tag else None

        date_tag = li.select_one("span.postdate span.date")
        date_text = date_tag.get_text(" ", strip=True) if date_tag else None
        date_text = normalize_date(date_text)

        counter_tag = li.select_one("a.postcounter")
        post_number = counter_tag.get_text(strip=True) if counter_tag else None

        quoted_author, quoted_post_id = extract_quote_info(msg_tag)
        text = clean_message_html(msg_tag)

        posts.append({
            "page": page_num,
            "post_id": post_id,
            "post_number": post_number,
            "author": author,
            "date": date_text,
            "quoted_author": quoted_author,
            "quoted_post_id": quoted_post_id,
            "text": text,
        })

    return posts


def load_done_pages(pages_dir: Path) -> set:
    done = set()
    for f in pages_dir.glob("page_*.json"):
        m = re.match(r"page_(\d+)\.json$", f.name)
        if m:
            done.add(int(m.group(1)))
    return done


def rebuild_jsonl(pages_dir: Path, jsonl_path: Path) -> int:
    """Baut posts.jsonl komplett neu aus den einzelnen pages/page_XXXX.json-Dateien auf.
    Dadurch ist die jsonl-Datei immer konsistent mit dem aktuellen Stand von pages/,
    unabhaengig davon, welche Seiten in diesem oder frueheren Laeufen neu geholt wurden."""
    all_posts = {}
    page_files = sorted(
        pages_dir.glob("page_*.json"),
        key=lambda p: int(re.match(r"page_(\d+)\.json$", p.name).group(1)),
    )
    for f in page_files:
        for post in json.loads(f.read_text(encoding="utf-8")):
            all_posts[post["post_id"]] = post

    ordered = sorted(all_posts.values(), key=lambda p: int(p["post_id"]))
    with jsonl_path.open("w", encoding="utf-8") as jsonl_file:
        for post in ordered:
            jsonl_file.write(json.dumps(post, ensure_ascii=False) + "\n")
    return len(ordered)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="thread_archive", help="Zielverzeichnis")
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--end-page", type=int, default=None, help="Standard: automatisch erkannte letzte Seite")
    parser.add_argument("--delay", type=float, default=2.0, help="Basiswartezeit in Sekunden zwischen Requests")
    parser.add_argument("--force", action="store_true", help="Bereits heruntergeladene Seiten erneut laden")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()

    print(f"Lade Seite 1 von {BASE_URL} ...")
    first_html = fetch(session, page_url(1))
    total_pages = detect_total_pages(first_html)
    end_page = args.end_page or total_pages
    print(f"Thread hat insgesamt {total_pages} Seiten. Verarbeite Seiten {args.start_page} bis {end_page}.")

    title_match = re.search(r"<title>([^<]*)</title>", first_html)
    meta = {
        "thread_url": BASE_URL,
        "title": title_match.group(1).strip() if title_match else None,
        "total_pages_detected": total_pages,
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    done_pages = set() if args.force else load_done_pages(pages_dir)

    for page_num in range(args.start_page, end_page + 1):
        page_file = pages_dir / f"page_{page_num:04d}.json"

        if page_num in done_pages:
            print(f"Seite {page_num}/{end_page} bereits vorhanden - ueberspringe.")
            continue

        if page_num == 1:
            html = first_html
        else:
            print(f"Lade Seite {page_num}/{end_page} ...")
            html = fetch(session, page_url(page_num))

        posts = parse_posts(html, page_num)
        page_file.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {len(posts)} Beitraege gefunden.")

        if page_num < end_page:
            time.sleep(args.delay + random.uniform(0, 1.0))

    jsonl_path = out_dir / "posts.jsonl"
    total = rebuild_jsonl(pages_dir, jsonl_path)
    print(f"\nposts.jsonl neu aufgebaut aus {len(list(pages_dir.glob('page_*.json')))} Seiten-Dateien ({total} Beitraege).")
    print(f"Fertig. Ergebnisse in: {out_dir.resolve()}")
    print(f"  - {jsonl_path.name}: alle Beitraege, ein JSON-Objekt pro Zeile (fuer die Analyse)")
    print(f"  - pages/page_XXXX.json: Beitraege pro Forenseite")
    print(f"  - meta.json: Thread-Metadaten")


if __name__ == "__main__":
    main()
