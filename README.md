# La Gomera Foto-Quiz — Punkte-Explorer

Auswertung des Foto-Ratespiel-Threads ["Das La Gomera Foto-Quiz"](https://www.gomeraforum.de/showthread.php?1754-Das-La-Gomera-Foto-Quiz) aus dem gomeraforum.de: wer hat wann wie viele Punkte für richtig erratene Fotos bekommen.

**🔗 Live: https://stefanhillmann.github.io/gomera-foto-quiz-punkte/**

Durchsuchbare, filterbare Rangliste mit Punkten, gelösten Rätseln (Siegen) und Sonderpunkten pro Jahr, inklusive Diagrammen und Verlinkung zu den Original-Beiträgen im Forum.

## Pipeline

Die Daten wurden mit einer Reihe von Scripts erzeugt (mit Erlaubnis des Forenbetreibers):

1. `download_thread.py` — lädt alle Thread-Seiten herunter (`thread_archive/`)
2. `extract_points.py` — extrahiert Punktevergaben per lokalem LLM (LM Studio) aus den Beiträgen
3. `build_table.py` — normalisiert Teilnehmernamen und aggregiert die CSV-Tabelle (`thread_archive/punkte_tabelle.csv`)
4. `export_web_data.py` — exportiert die Daten als `docs/data/data.json` für das Web-Tool

Das Web-Tool selbst (`docs/`) ist reines HTML/CSS/JavaScript ohne Build-Schritt, mit Chart.js für die Diagramme, gehostet über GitHub Pages.

Die Webseite zeigt ausschließlich strukturierte Daten (Namen, Punkte, Daten, Links) — keine Forenbeiträge im Volltext.

## Aktualisierung

Wenn der Thread neue Seiten bekommen hat, in dieser Reihenfolge neu laufen lassen:

```bash
# 1. Neue Seiten nachladen (bereits geladene werden uebersprungen)
python3 download_thread.py

# 2. Punktevergaben aus den neuen Beitraegen extrahieren (LM Studio muss laufen)
python3 extract_points.py

# 3. Optional: CSV-Tabelle neu aufbauen (fuer den lokalen Ueberblick)
python3 build_table.py

# 4. Web-Tool-Daten neu exportieren
python3 export_web_data.py
```

Nach Schritt 4 kurz pruefen, ob `export_web_data.py` neue "nicht eindeutig zugeordnete Namen" meldet - falls ja, ggf. `ALIAS_MAP` in `build_table.py` ergaenzen und Schritt 3+4 wiederholen.

Danach das Ergebnis committen und pushen - die GitHub-Pages-Seite aktualisiert sich automatisch bei jedem Push auf `main`:

```bash
git add thread_archive/point_events.jsonl thread_archive/punkte_tabelle.csv docs/data/data.json
git commit -m "Daten aktualisiert"
git push
```
