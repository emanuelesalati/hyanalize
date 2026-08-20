# CLAUDE.md

## Project overview

**HYANALIZE** — piattaforma di analytics cross-evento per HYROX, pensata per atleti e coach.
Scarica TUTTI gli eventi HYROX mondiali (185+ gare, 3 stagioni, 1M+ risultati) via pyrox-client e offre analisi che nessun altro tool fornisce: progressione atleta nel tempo, classifiche cross-evento, confronti, pacing analysis, training insights.

Target: community Instagram **@hyroxitaliacommunity** + servizio per coach e atleti.

## Architecture

- **sync.py** — Scarica dati da results.hyrox.com via `pyrox-client` (gratuito, no API key). Salva un JSON per gara in `data/races/` + `dashboard.json` (solo eventi+stats). Source: CDN CloudFront AWS (`d2wl4b7sx66tfb.cloudfront.net`).
- **index.html** — Dashboard SPA (single-page app). Carica `dashboard.json` all'avvio, poi carica le singole gare on-demand via fetch.
- **GitHub Actions** — `.github/workflows/sync.yml` esegue sync giornaliero alle 06:00 UTC e committa i dati. Richiede `permissions: contents: write`.
- **data/** — Committato nel repo. `dashboard.json` (~360KB), `data/races/*.json` (~330MB totali, 1-8MB per gara).

## Data format

Ogni file `data/races/{key}.json` contiene un array di risultati con:
```
name, nationality, age_group, gender, division, total_time,
skiErg, sledPush, sledPull, burpee, row, farmersCarry, lunges, wallBalls,
run_time, work_time, roxzone,
run1, run2, run3, run4, run5, run6, run7, run8
```
- I tempi sono in **minuti** (float), non millisecondi.
- I nomi sono nel formato "Nome Cognome" (convertiti da "Cognome, Nome" nel sync).
- La chiave file gara: `s{season}_{location}_{year}` (es. `s8_rimini_2026`).

## Development rules

### Errori da NON ripetere

1. **MAI aprire index.html come `file://`** — i fetch falliscono per CORS. Usare SEMPRE il server HTTP locale:
   ```bash
   python -c "from http.server import HTTPServer,SimpleHTTPRequestHandler;from socketserver import ThreadingMixIn;class T(ThreadingMixIn,HTTPServer):pass;T(('',8080),SimpleHTTPRequestHandler).serve_forever()"
   ```
   Poi aprire `http://localhost:8080`. Il server DEVE essere threaded per gestire fetch paralleli.

2. **MAI mettere `</script>` dentro un template literal JS** — il parser HTML lo interpreta come chiusura del tag script principale e rompe tutta la pagina. Usare variabili JS dirette o `<\/script>`.

3. **Encoding UTF-8 obbligatorio** su Windows:
   - Python: `PYTHONIOENCODING=utf-8` nel comando
   - File open: sempre `encoding='utf-8'`

4. **Nomi atleti**: formato "Nome Cognome". La funzione `fix_name()` in sync.py converte "Cognome, Nome" → "Nome Cognome". Per la ricerca atleta, splittare le parole e cercare con `words.every(w => name.includes(w))`.

5. **GitHub Actions**: il workflow richiede `permissions: contents: write` per fare git push. Senza questo, exit code 128.

6. **Canvas ID univoci**: quando si generano più elementi con Canvas (grafiche, radar, istogrammi), ogni elemento deve avere un ID univoco. Mai riusare `id="ig-canvas"` in un loop.

7. **Testare SEMPRE** le modifiche al frontend nel browser prima di dichiarare fatto.

8. **pyrox-client** non è un'API REST — legge file Parquet da un CDN CloudFront. Non ha rate limiting ma i dati sono statici (aggiornati da HYROX).

### Setup development

```bash
pip install -r requirements.txt
PYTHONIOENCODING=utf-8 SEASONS_TO_SCAN=1 python sync.py  # test rapido
# Server locale:
python -c "from http.server import HTTPServer,SimpleHTTPRequestHandler;from socketserver import ThreadingMixIn;class T(ThreadingMixIn,HTTPServer):pass;T(('',8080),SimpleHTTPRequestHandler).serve_forever()"
```

### Environment variables

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `SEASONS_TO_SCAN` | Numero di stagioni da scansionare | `3` |

### File structure

```
sync.py              — Data sync script
index.html           — Dashboard SPA
requirements.txt     — pyrox-client>=0.2.7
data/dashboard.json  — Eventi + stats (leggero)
data/races/*.json    — Risultati per gara (on-demand)
.github/workflows/   — Sync giornaliero
```
