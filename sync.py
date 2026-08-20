"""
Hyrox Content Engine – Data Sync Script

Scarica TUTTI gli eventi HYROX mondiali via pyrox-client (gratuito, no API key).
Salva un file JSON per ogni gara + un dashboard.json leggero (solo eventi e stats).
"""

import json
import os
from datetime import datetime
from pathlib import Path

import pyrox

# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

# Stagioni da scansionare (ultime N). Sovrascrivibile via env.
SEASONS_TO_SCAN = int(os.getenv("SEASONS_TO_SCAN", "3"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def save_json(data, filename: str):
    """Salva dati come JSON nella cartella data/."""
    filepath = DATA_DIR / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"  💾 {filepath}")


def race_file_key(season, location, year):
    """Genera la chiave univoca per un file di gara."""
    return f"s{season}_{location}_{year}"


def fix_name(name):
    """Converte 'Cognome, Nome' → 'Nome Cognome'."""
    if not name or not isinstance(name, str):
        return name
    if ", " in name:
        parts = name.split(", ", 1)
        return f"{parts[1]} {parts[0]}"
    return name


def df_to_results(df):
    """Converte un DataFrame pyrox in lista di dict leggeri."""
    rows = []
    for _, r in df.iterrows():
        def val(col):
            v = r.get(col)
            if v is None or (isinstance(v, float) and v != v):
                return None
            return round(v, 2) if isinstance(v, float) else v

        rows.append({
            "name": fix_name(val("name")),
            "nationality": val("nationality"),
            "age_group": val("age_group"),
            "gender": val("gender"),
            "division": val("division"),
            "total_time": val("total_time"),
            "skiErg": val("skiErg_time"),
            "sledPush": val("sledPush_time"),
            "sledPull": val("sledPull_time"),
            "burpee": val("burpeeBroadJump_time"),
            "row": val("rowErg_time"),
            "farmersCarry": val("farmersCarry_time"),
            "lunges": val("sandbagLunges_time"),
            "wallBalls": val("wallBalls_time"),
            "run_time": val("run_time"),
            "work_time": val("work_time"),
            "roxzone": val("roxzone_time"),
            "run1": val("run1_time"),
            "run2": val("run2_time"),
            "run3": val("run3_time"),
            "run4": val("run4_time"),
            "run5": val("run5_time"),
            "run6": val("run6_time"),
            "run7": val("run7_time"),
            "run8": val("run8_time"),
        })
    return rows


def calc_stats(results):
    """Calcola statistiche per divisione+genere da una lista di risultati."""
    groups = {}
    for r in results:
        gk = f"{r['division']}_{r['gender']}"
        groups.setdefault(gk, []).append(r)

    stats = {}
    for gk, group in groups.items():
        times = sorted([r["total_time"] for r in group if r["total_time"]])
        if not times:
            continue
        n = len(times)
        stats[gk] = {
            "division": group[0]["division"],
            "gender": group[0]["gender"],
            "count": n,
            "min": round(times[0], 2),
            "max": round(times[-1], 2),
            "avg": round(sum(times) / n, 2),
            "median": round(times[n // 2], 2),
            "p10": round(times[int(n * 0.1)], 2) if n >= 10 else None,
            "p25": round(times[int(n * 0.25)], 2) if n >= 4 else None,
            "p75": round(times[int(n * 0.75)], 2) if n >= 4 else None,
            "p90": round(times[int(n * 0.9)], 2) if n >= 10 else None,
        }
    return stats


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

def sync():
    print("🚀 Hyrox Content Engine – Sync avviato (pyrox-client)")
    print(f"   Stagioni da scansionare: {SEASONS_TO_SCAN}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    client = pyrox.PyroxClient()

    # 1. Scopri stagioni e gare disponibili
    all_seasons = client.list_seasons()
    target_seasons = sorted(all_seasons, reverse=True)[:SEASONS_TO_SCAN]
    print(f"   Stagioni: {target_seasons}")

    all_races = []
    for season in target_seasons:
        races = client.list_races(season=season)
        for _, row in races.iterrows():
            all_races.append({
                "season": int(row["season"]),
                "location": row["location"],
                "year": int(row["year"]) if row.get("year") else None,
            })

    print(f"\n📅 Trovate {len(all_races)} gare in {len(target_seasons)} stagioni")

    # 2. Scarica risultati per ogni gara → un file JSON per gara
    events_summary = []

    for i, race in enumerate(all_races):
        season = race["season"]
        location = race["location"]
        year = race["year"]
        key = race_file_key(season, location, year)
        label = f"{location} {year}" if year else location
        print(f"\n🏟️  [{i+1}/{len(all_races)}] Season {season} — {label}")

        try:
            df = client.get_race(season=season, location=location, year=year)
        except Exception as e:
            print(f"  ⚠️  Errore: {e}")
            continue

        if df.empty:
            print(f"  (vuoto)")
            continue

        count = len(df)
        print(f"  {count} risultati")

        # Converti e salva risultati in file separato
        results = df_to_results(df)
        save_json(results, f"races/{key}.json")

        # Calcola stats per questo evento
        event_stats = calc_stats(results)

        # Divisioni e generi disponibili
        divisions = sorted(df["division"].dropna().unique().tolist()) if "division" in df.columns else []
        genders = sorted(df["gender"].dropna().unique().tolist()) if "gender" in df.columns else []

        event_info = {
            "season": season,
            "location": location,
            "year": year,
            "key": key,
            "name": df["event_name"].iloc[0] if "event_name" in df.columns else label,
            "results_count": count,
            "divisions": divisions,
            "genders": genders,
            "stats": event_stats,
        }
        events_summary.append(event_info)

    # 3. Genera dashboard.json (leggero: solo eventi + stats, NO risultati)
    print("\n📊 Genero dashboard.json...")
    dashboard = {
        "last_sync": timestamp,
        "events": events_summary,
    }
    save_json(dashboard, "dashboard.json")

    print(f"\n✅ Sync completato!")
    print(f"   Timestamp: {timestamp}")
    print(f"   Gare: {len(events_summary)}")
    size_mb = (DATA_DIR / "dashboard.json").stat().st_size / 1024 / 1024
    print(f"   dashboard.json: {size_mb:.1f} MB")


if __name__ == "__main__":
    sync()
