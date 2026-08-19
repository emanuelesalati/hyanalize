"""
Hyrox Content Engine – Data Sync Script

Scarica eventi, risultati, split e statistiche dalla Hyrox Result API
e salva tutto in /data come JSON e CSV pronti per la creazione di contenuti.
"""

import os
import sys
import json
import csv
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------

load_dotenv()

API_BASE = "https://hyroxresultapi.com/api/v1"
TOKEN = os.getenv("HYROX_API_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json",
}

DATA_DIR = Path(__file__).parent / "data"

# Città italiane da cercare negli eventi (l'API non popola country_code)
ITALIAN_CITIES = ["rimini", "milan", "roma", "rome", "napol", "torin", "firenz",
                  "florence", "venezia", "venice", "bolog", "genova", "verona"]

# Stagioni da scansionare (ultime N). Sovrascrivibile via env.
SEASONS_TO_SCAN = int(os.getenv("SEASONS_TO_SCAN", "3"))

# Rate-limit: pausa tra richieste (secondi) per restare sotto 30 req/min
# Piano Starter = 30 req/min → 1 ogni 2s, usiamo 3s per sicurezza
REQUEST_DELAY = 3.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def api_get(path: str, params: dict | None = None) -> dict:
    """GET con gestione errori e rate-limit."""
    url = f"{API_BASE}{path}"
    time.sleep(REQUEST_DELAY)
    resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
    for attempt in range(3):
        if resp.status_code != 429:
            break
        retry_after = int(resp.headers.get("Retry-After", 60))
        print(f"  ⏳ Rate-limited, attendo {retry_after}s (tentativo {attempt + 1}/3)...")
        time.sleep(retry_after)
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def save_json(data, filename: str):
    """Salva dati come JSON nella cartella data/."""
    filepath = DATA_DIR / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  💾 {filepath}")


def save_csv(rows: list[dict], filename: str):
    """Salva lista di dict come CSV nella cartella data/."""
    if not rows:
        return
    filepath = DATA_DIR / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  💾 {filepath}")


def ms_to_time(ms) -> str:
    """Converte millisecondi in formato HH:MM:SS o MM:SS."""
    if ms is None:
        return ""
    total_seconds = int(ms) // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


# ---------------------------------------------------------------------------
# Step 1: Recupera eventi recenti per i paesi di interesse
# ---------------------------------------------------------------------------

def fetch_events() -> list[dict]:
    """Scarica eventi italiani cercando per città nelle ultime stagioni."""
    # Recupera stagioni disponibili
    seasons_data = api_get("/seasons")
    all_seasons = seasons_data.get("data", [])
    # Prendi le ultime N stagioni (ordinate per sort_order)
    recent_seasons = sorted(all_seasons, key=lambda s: s.get("sort_order", 0), reverse=True)[:SEASONS_TO_SCAN]

    all_events = []
    for season in recent_seasons:
        slug = season["slug"]
        label = season.get("label", slug)
        print(f"\n📅 Scansiono {label} ({slug})...")
        data = api_get("/events", params={"season": slug})
        events = data.get("data", [])

        # Filtra per città italiane
        italian = []
        for e in events:
            city = (e.get("city") or "").lower()
            if any(kw in city for kw in ITALIAN_CITIES):
                italian.append(e)

        if italian:
            print(f"  Trovati {len(italian)} eventi italiani")
            all_events.extend(italian)
        else:
            print(f"  Nessun evento italiano")

    return all_events


# ---------------------------------------------------------------------------
# Step 2: Per ogni evento, scarica divisioni e risultati
# ---------------------------------------------------------------------------

def fetch_divisions(event_slug: str) -> list[dict]:
    """Scarica le divisioni di un evento."""
    data = api_get(f"/events/{event_slug}/divisions")
    return data.get("data", [])


def fetch_results(division_id: int, max_pages: int = 100) -> list[dict]:
    """Scarica risultati paginati di una divisione (cursor pagination)."""
    all_results = []
    cursor = None

    for page in range(max_pages):
        params = {}
        if cursor:
            params["cursor"] = cursor
        data = api_get(f"/divisions/{division_id}/results", params=params)
        results = data.get("data", [])
        all_results.extend(results)

        # Cursor pagination: meta.cursor + meta.has_more
        meta = data.get("meta", {})
        if not meta.get("has_more") or not results:
            break
        cursor = meta.get("cursor")

    return all_results


# ---------------------------------------------------------------------------
# Step 3: Scarica statistiche precalcolate per divisione
# ---------------------------------------------------------------------------

def fetch_division_stats(division_id: int) -> dict | None:
    """Scarica statistiche (medie, percentili, ecc.) di una divisione."""
    try:
        data = api_get(f"/stats/divisions/{division_id}")
        return data.get("data")
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            print(f"  ⚠️  Stats non disponibili per divisione {division_id}")
            return None
        raise


# ---------------------------------------------------------------------------
# Step 4: Scarica split per i top atleti
# ---------------------------------------------------------------------------

def search_athlete(surname: str, first_name: str) -> list[dict]:
    """Cerca un atleta per nome e cognome, ritorna i race ID."""
    try:
        data = api_get("/athletes/search", params={"q": surname, "first": first_name})
        return data.get("data", [])
    except requests.HTTPError:
        return []


def fetch_athlete_splits(race_id: str) -> list[dict]:
    """Scarica gli split stazione per stazione dato un race ID (base64)."""
    try:
        data = api_get(f"/athletes/{race_id}/splits")
        return data.get("data", [])
    except requests.HTTPError:
        return []


# ---------------------------------------------------------------------------
# Main sync
# ---------------------------------------------------------------------------

def sync():
    if not TOKEN:
        print("❌ HYROX_API_TOKEN non trovato. Crea un file .env con:")
        print('   HYROX_API_TOKEN=il_tuo_token')
        sys.exit(1)

    print("🚀 Hyrox Content Engine – Sync avviato")
    print(f"   Stagioni da scansionare: {SEASONS_TO_SCAN}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. Recupera eventi
    events = fetch_events()
    if not events:
        print("\n⚠️  Nessun evento trovato. Prova ad aumentare LOOKBACK_DAYS.")
        return

    save_json(events, f"events_{timestamp}.json")

    # 2. Per ogni evento, scarica divisioni + risultati + stats
    all_results_flat = []

    for event in events:
        slug = event.get("slug", "")
        name = event.get("name", slug)
        print(f"\n🏟️  Evento: {name} ({slug})")

        divisions = fetch_divisions(slug)
        save_json(divisions, f"divisions/{slug}_{timestamp}.json")

        for div in divisions:
            div_id = div.get("id")
            div_name = div.get("name", div.get("label", str(div_id)))
            print(f"\n  📊 Divisione: {div_name} (id={div_id})")

            # Risultati
            results = fetch_results(div_id)
            print(f"     {len(results)} risultati scaricati")

            if results:
                # Aggiungi contesto evento/divisione a ogni riga
                for r in results:
                    r["_event_slug"] = slug
                    r["_event_name"] = name
                    r["_division_name"] = div_name
                    r["_division_id"] = div_id
                all_results_flat.extend(results)

                save_json(results, f"results/{slug}_{div_id}_{timestamp}.json")

            # Statistiche
            stats = fetch_division_stats(div_id)
            if stats:
                save_json(stats, f"stats/{slug}_{div_id}_{timestamp}.json")

    # 3. Salva CSV riepilogativo con tutti i risultati
    if all_results_flat:
        # Estrai campi principali per il CSV
        csv_rows = []
        for r in all_results_flat:
            csv_rows.append({
                "event": r.get("_event_name", ""),
                "event_slug": r.get("_event_slug", ""),
                "division": r.get("_division_name", ""),
                "rank": r.get("rank_overall", r.get("rank", "")),
                "athlete_name": r.get("athlete_name", r.get("name", "")),
                "athlete_id": r.get("athlete_id", r.get("id", "")),
                "nationality": r.get("nationality", ""),
                "age_group": r.get("age_group", ""),
                "total_time_ms": r.get("total_time_ms", r.get("total_time", "")),
                "total_time": ms_to_time(r.get("total_time_ms", r.get("total_time"))),
                "bib": r.get("bib", ""),
            })
        save_csv(csv_rows, f"all_results_{timestamp}.csv")

    # 4. Split dei top 10 per ogni divisione (per contenuti "testa a testa")
    # L'API richiede un race ID (base64) per gli split, ottenibile via search per nome.
    print("\n🏃 Scarico split dei top atleti...")
    top_splits = []
    seen_names = set()

    for r in all_results_flat:
        rank = r.get("rank_overall", r.get("rank", 999))
        athlete_name = r.get("athlete_name", r.get("name", ""))
        if rank is None or int(rank) > 10 or not athlete_name or athlete_name in seen_names:
            continue
        seen_names.add(athlete_name)

        # Nome nel formato "Cognome, Nome"
        parts = athlete_name.split(", ", 1)
        if len(parts) != 2:
            continue
        surname, first = parts

        # Cerca l'atleta per ottenere il race ID
        search_results = search_athlete(surname, first)
        # Trova il race ID corrispondente all'evento
        event_slug = r.get("_event_slug", "")
        race_id = None
        for sr in search_results:
            if sr.get("event_slug") == event_slug:
                race_id = sr.get("id")
                break
        if not race_id and search_results:
            race_id = search_results[0].get("id")  # fallback: prima gara trovata

        if race_id:
            splits = fetch_athlete_splits(race_id)
            if splits:
                for s in splits:
                    s["_athlete_name"] = athlete_name
                    s["_event_slug"] = event_slug
                    s["_division_name"] = r.get("_division_name", "")
                top_splits.extend(splits)

    if top_splits:
        save_json(top_splits, f"splits_top10_{timestamp}.json")
        print(f"  {len(top_splits)} split scaricati per {len(seen_names)} atleti")

    # 5. Genera dashboard.json consolidato per la dashboard web
    print("\n📊 Genero dashboard.json...")
    # Raccogli stats per divisione
    all_stats = {}
    for event in events:
        slug = event.get("slug", "")
        for fname in (DATA_DIR / "stats").glob(f"{slug}_*_{timestamp}.json"):
            with open(fname, encoding="utf-8") as f:
                stat = json.load(f)
                div_id = fname.stem.split("_")[1]  # slug_divid_timestamp
                all_stats[f"{slug}_{div_id}"] = stat

    dashboard = {
        "last_sync": timestamp,
        "events": events,
        "results": all_results_flat,
        "stats": all_stats,
        "splits": top_splits,
    }
    save_json(dashboard, "dashboard.json")

    print(f"\n✅ Sync completato! Dati salvati in {DATA_DIR}/")
    print(f"   Timestamp: {timestamp}")
    print(f"   Eventi: {len(events)}")
    print(f"   Risultati totali: {len(all_results_flat)}")


if __name__ == "__main__":
    sync()
