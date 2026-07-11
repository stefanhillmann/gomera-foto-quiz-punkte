#!/usr/bin/env python3
"""
Phase 2+3 der Punkte-Auswertung: filtert Kandidaten-Posts (die das Wort "Punkt"
enthalten) aus thread_archive/posts.jsonl und laesst ein lokales LLM (LM Studio,
OpenAI-kompatible API) daraus strukturiert extrahieren, wer wie viele Punkte
bekommen hat.

Voraussetzung: LM Studio laeuft mit geladenem Modell und lokalem Server
(Standard: http://localhost:1234).

Beispiel:
    python3 extract_points.py
    python3 extract_points.py --model google/gemma-4-12b-qat --limit 20
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"

SCHEMA = {
    "type": "object",
    "properties": {
        "vergaben": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "empfaenger": {"type": "string"},
                    "gesamtpunkte": {"type": "integer"},
                    "davon_sonderpunkte": {"type": "integer"},
                },
                "required": ["empfaenger", "gesamtpunkte", "davon_sonderpunkte"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["vergaben"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """Du wertest Beitraege aus einem Foto-Ratespiel-Forum aus (La Gomera Foto-Quiz).
Regeln des Spiels: Ein Teilnehmer stellt ein Foto eines Ortes ein. Wer den Ort erraet,
bekommt vom Ersteller des Bildes eine Punktzahl zugesprochen (meist genannt im Beitrag
des Bilder-Erstellers). Manchmal kommt zur Grundpunktzahl noch ein Sonderpunkt/Extrapunkt
dazu (z.B. fuers Bild-Drehen). Der Empfaenger wird oft nicht namentlich genannt, sondern
ist die Person, auf deren Beitrag geantwortet wird (Feld 'Antwort auf' im Kontext).

WICHTIGE REGELN:
1. Wenn in diesem Beitrag KEINE tatsaechliche Punktevergabe stattfindet, gib GENAU
   {"vergaben": []} zurueck (leere Liste) - keinen Platzhalter-Eintrag.
2. Pro Empfaenger GENAU EIN Eintrag mit der GESAMTEN in diesem Beitrag fuer ihn
   genannten Punktzahl (gesamtpunkte). Falls davon ein Teil ausdruecklich als
   Sonderpunkt/Extrapunkt bezeichnet wird, trage diesen Teilbetrag zusaetzlich in
   davon_sonderpunkte ein (0 wenn kein Sonderpunkt genannt wird). davon_sonderpunkte
   ist IMMER Teil von gesamtpunkte, nicht zusaetzlich dazu.
   Beispiel: "100 Punkte, dazu noch ein Extrapunkt, macht 101" -> gesamtpunkte=101,
   davon_sonderpunkte=1.
3. Erfinde keine Empfaenger oder Punkte, die nicht im Text stehen. Wenn der Text nur
   informell mit "du"/"dir"/"dich" auf jemanden verweist (kein Name, kein Zitat), aber
   im Kontext ein "Vorheriger Beitrag im Thread" angegeben ist, ist dessen Autor mit
   hoher Wahrscheinlichkeit der gemeinte Empfaenger - nimm dann diesen Namen.
4. Wenn sich trotz "Vorheriger Beitrag"-Kontext kein Empfaenger sicher bestimmen laesst,
   nimm den Namen aus dem vorherigen Beitrag trotzdem als beste Vermutung.
5. GANZ WICHTIG: Der Autor des aktuellen Beitrags ist NIEMALS gleichzeitig der
   Empfaenger einer Punktevergabe in diesem Beitrag. Unterscheide dabei klar zwei
   Faelle, die beide eine Punktzahl im Text enthalten koennen:
   a) Der Autor BEWERTET/BESTAETIGT gerade einen Rateversuch und vergibt dafuer
      Punkte, z.B. "Stimmt, 100 Punkte!", "Richtig, 50 Punkte fuer dich",
      "Erraten, macht 105 Punkte". Das IST eine echte, neue Vergabe - Empfaenger ist
      die Person, deren Rateversuch bestaetigt wird (meist Autor des vorherigen
      Beitrags, siehe Kontext).
   b) Der Autor bedankt sich NUR fuer Punkte, die er selbst SOEBEN vom vorherigen
      Beitrag bekommen hat, z.B. "Danke fuer die Punkte", "Danke fuer die 100
      Punkte", "Vielen Dank fuer die Punkte". Das ist KEINE neue Vergabe, sondern nur
      ein Dank fuer eine bereits im vorherigen Beitrag vergebene Punktzahl - hier
      IMMER {"vergaben": []} zurueckgeben, auch wenn eine Punktzahl im Text steht.
   Merkhilfe: Bei (a) bewertet/vergibt der Autor aktiv etwas fuer eine andere Person.
   Bei (b) ist der Autor selbst der (bereits bediente) Empfaenger und sagt nur danke.
"""

CANDIDATE_RE = re.compile(r"p[uü]nkt|puntos?\b", re.IGNORECASE)


def load_posts(jsonl_path: Path):
    posts = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            posts.append(json.loads(line))
    return posts


def find_previous_different_author(post, sorted_posts, pos_by_id):
    """Sucht den naechsten vorherigen Beitrag eines ANDEREN Autors im Thread -
    das ist bei fehlendem Zitat oft die Person, auf die informell geantwortet wird."""
    idx = pos_by_id[post["post_id"]]
    for j in range(idx - 1, -1, -1):
        candidate = sorted_posts[j]
        if candidate["author"] != post["author"]:
            return candidate
    return None


def build_user_message(post, posts_by_id, sorted_posts, pos_by_id):
    lines = [f"Autor des Beitrags: {post['author']}"]
    if post.get("quoted_author"):
        lines.append(f"Antwort auf einen Beitrag von: {post['quoted_author']}")
        quoted = posts_by_id.get(post.get("quoted_post_id"))
        if quoted and quoted.get("text"):
            lines.append(f"Zitierter Beitrag (Ausschnitt): {quoted['text'][:200]}")
    else:
        prev = find_previous_different_author(post, sorted_posts, pos_by_id)
        if prev and prev.get("text"):
            lines.append(
                f"Vorheriger Beitrag im Thread (von {prev['author']}, "
                f"moeglicherweise der Rateversuch, auf den geantwortet wird): "
                f"{prev['text'][:200]}"
            )
    lines.append(f"Beitragstext:\n{post['text']}")
    return "\n".join(lines)


def call_model(model: str, user_message: str, retries: int = 2):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "punkte_extraktion", "strict": True, "schema": SCHEMA},
        },
    }
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(LM_STUDIO_URL, json=payload, timeout=120)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return parsed
        except (requests.RequestException, KeyError, json.JSONDecodeError) as e:
            last_err = e
            print(f"    Fehler bei Modellaufruf (Versuch {attempt}/{retries}): {e}", file=sys.stderr)
            time.sleep(2)
    raise RuntimeError(f"Modellaufruf endgueltig fehlgeschlagen: {last_err}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="thread_archive/posts.jsonl")
    parser.add_argument("--output", default="thread_archive/point_events.jsonl")
    parser.add_argument("--failed-log", default="thread_archive/point_events_failed.jsonl")
    parser.add_argument("--model", default="google/gemma-4-12b-qat")
    parser.add_argument("--limit", type=int, default=None, help="Nur die ersten N Kandidaten verarbeiten (zum Testen)")
    args = parser.parse_args()

    posts = load_posts(Path(args.input))
    posts_by_id = {p["post_id"]: p for p in posts}
    sorted_posts = sorted(posts, key=lambda p: int(p["post_id"]))
    pos_by_id = {p["post_id"]: i for i, p in enumerate(sorted_posts)}
    candidates = [p for p in posts if CANDIDATE_RE.search(p["text"])]
    if args.limit:
        candidates = candidates[: args.limit]

    print(f"{len(posts)} Beitraege geladen, {len(candidates)} Kandidaten (enthalten 'Punkt').")

    events = []
    failed = []
    no_result_candidates = []

    out_path = Path(args.output)
    failed_path = Path(args.failed_log)
    review_path = out_path.parent / "point_events_review.jsonl"

    with out_path.open("w", encoding="utf-8") as out_f, \
         failed_path.open("w", encoding="utf-8") as fail_f, \
         review_path.open("w", encoding="utf-8") as review_f:
        for i, post in enumerate(candidates, 1):
            print(f"[{i}/{len(candidates)}] Post {post['post_id']} ({post['date']}) ...")
            has_quote = bool(post.get("quoted_author"))
            prev_post = None if has_quote else find_previous_different_author(post, sorted_posts, pos_by_id)
            user_message = build_user_message(post, posts_by_id, sorted_posts, pos_by_id)
            try:
                result = call_model(args.model, user_message)
            except RuntimeError as e:
                print(f"  UEBERSPRUNGEN: {e}", file=sys.stderr)
                fail_f.write(json.dumps({"post_id": post["post_id"], "error": str(e)}, ensure_ascii=False) + "\n")
                failed.append(post["post_id"])
                continue

            vergaben = [
                v for v in result.get("vergaben", [])
                if v.get("empfaenger") and v.get("gesamtpunkte", 0) > 0
            ]

            # Sicherheitsnetz: Autor == Empfaenger ist in diesem Spiel strukturell nie
            # eine echte Vergabe (siehe Prompt-Regel 5) - trotzdem geloggt, nicht nur verworfen.
            self_awards = [v for v in vergaben if v["empfaenger"] == post["author"]]
            vergaben = [v for v in vergaben if v["empfaenger"] != post["author"]]
            for v in self_awards:
                review_f.write(json.dumps({
                    "grund": "melder_gleich_empfaenger_automatisch_verworfen",
                    "post_id": post["post_id"], "date": post["date"], "author": post["author"],
                    "verworfene_vergabe": v, "text": post["text"],
                }, ensure_ascii=False) + "\n")

            if not vergaben:
                no_result_candidates.append(post["post_id"])
                review_f.write(json.dumps({
                    "grund": "kandidat_ohne_ergebnis",
                    "post_id": post["post_id"], "date": post["date"], "author": post["author"],
                    "quoted_author": post.get("quoted_author"),
                    "vorheriger_beitrag_von": prev_post["author"] if prev_post else None,
                    "text": post["text"],
                }, ensure_ascii=False) + "\n")

            for vergabe in vergaben:
                kontext_quelle = "zitat" if has_quote else (
                    "vorheriger_beitrag" if vergabe["empfaenger"] == (prev_post["author"] if prev_post else None) else "text"
                )
                event = {
                    "post_id": post["post_id"],
                    "page": post["page"],
                    "date": post["date"],
                    "year": post["date"].split(".")[-1].split(",")[0].strip() if post.get("date") else None,
                    "melder": post["author"],
                    "empfaenger": vergabe["empfaenger"],
                    "gesamtpunkte": vergabe["gesamtpunkte"],
                    "davon_sonderpunkte": vergabe.get("davon_sonderpunkte", 0),
                    "kontext_quelle": kontext_quelle,
                }
                events.append(event)
                out_f.write(json.dumps(event, ensure_ascii=False) + "\n")

                flags = []
                if event["melder"] == event["empfaenger"]:
                    flags.append("melder_gleich_empfaenger")
                if kontext_quelle == "vorheriger_beitrag":
                    flags.append("empfaenger_nur_ueber_fallback")
                if event["davon_sonderpunkte"] > event["gesamtpunkte"]:
                    flags.append("sonderpunkte_groesser_gesamt")
                if event["gesamtpunkte"] > 200:
                    flags.append("ungewoehnlich_hohe_punktzahl")
                if flags:
                    review_f.write(json.dumps({
                        "grund": flags, "event": event,
                        "quoted_author": post.get("quoted_author"),
                        "vorheriger_beitrag_von": prev_post["author"] if prev_post else None,
                        "text": post["text"],
                    }, ensure_ascii=False) + "\n")
            out_f.flush()
            review_f.flush()

    print(f"\nFertig. {len(events)} Punkte-Ereignisse extrahiert aus {len(candidates)} Kandidaten.")
    print(f"  - {out_path}: extrahierte Punkte-Ereignisse")
    print(f"  - {review_path}: zu pruefende Faelle ({len(no_result_candidates)} ohne Ergebnis + geflaggte Events)")
    if failed:
        print(f"  - {failed_path}: {len(failed)} fehlgeschlagene Posts (Post-IDs: {failed})")


if __name__ == "__main__":
    main()
