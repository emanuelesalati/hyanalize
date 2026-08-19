# CLAUDE.md

## Project overview

Hyrox Content Engine ("hyanalize") — motore di contenuti automatico per la community Instagram **Hyroxitaliacommunity**. Scarica dati reali dalle gare HYROX italiane (tempi, split, percentili, classifiche) e li salva come dataset strutturato (JSON + CSV) pronto per creare contenuti Instagram (post/stories).

Fase attuale: **MVP / validazione** — sync dati + contenuti manuali su Canva. Niente generazione grafica automatica né collegamento atleti-palestre (roadmap futura).

## Architecture

- **sync.py** — Script principale. Chiama la Hyrox Result API, scarica eventi italiani, risultati per divisione, statistiche precalcolate e split dei top atleti. Salva in `data/`.
- **Hyrox Result API** — REST API non ufficiale (`hyroxresultapi.com/api/v1`). Auth via Bearer token. Piano Starter: 30 req/min. Docs: `hyroxresultapi.com/llms.txt`.
- **GitHub Actions** — `.github/workflows/sync.yml` esegue `sync.py` ogni giorno alle 06:00 UTC e commita i nuovi dati.
- **data/** — Output committato nel repo. JSON per divisioni/risultati/stats/split, CSV riepilogativo.

## Key API quirks

- `country_code` non è popolato negli eventi: gli eventi italiani si identificano cercando città italiane nel campo `city` (es. "2025 Rimini").
- Gli split richiedono un **race ID base64** (ottenuto via `/athletes/search`), non l'`athlete_id` ULID presente nei risultati di divisione.
- Pagination: cursor-based via `meta.cursor` + `meta.has_more` (non `next_cursor`).
- `parse_status: "list_only"` indica che i dati dettagliati dell'atleta non sono ancora disponibili.

## Development setup

```bash
# 1. Crea .env con il token API (MAI committare)
echo "HYROX_API_TOKEN=<token>" > .env

# 2. Installa dipendenze
pip install -r requirements.txt

# 3. Esegui sync
PYTHONIOENCODING=utf-8 python sync.py
```

Su Windows serve `PYTHONIOENCODING=utf-8` per gli emoji nell'output.

## Environment variables

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `HYROX_API_TOKEN` | Token Bearer per l'API (obbligatorio) | — |
| `SEASONS_TO_SCAN` | Numero di stagioni da scansionare | `3` |

## Security rules

- Il token API **non deve mai** finire in file committati.
- `.env` è nel `.gitignore`.
- Il token in CI è in GitHub Secrets (`HYROX_API_TOKEN`).

## Common tasks

- **Aggiungere una città italiana**: aggiungi la keyword in `ITALIAN_CITIES` in `sync.py`.
- **Cambiare frequenza sync**: modifica il cron in `.github/workflows/sync.yml`.
- **Test rapido**: `PYTHONIOENCODING=utf-8 SEASONS_TO_SCAN=1 python sync.py`.
