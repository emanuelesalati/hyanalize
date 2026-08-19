# Progetto: Hyrox Content Engine

## Contesto generale

Gestisco due community italiane legate al mondo Hybrid/HYROX:

1. **Italian Hybrid Community (IHC)** — piattaforma che mappa palestre/box affiliate in Italia (sito: italianhybridcommunity.it). Le strutture inviano i propri dati via un modulo Word (foto, orari, staff, discipline offerte, ecc.) e vengono pubblicate sul sito con una scheda dedicata.
2. **Hyroxitaliacommunity** — community IG dedicata agli atleti italiani di HYROX, dove voglio lanciare questo nuovo servizio.

## Obiettivo del progetto

Creare un motore di contenuti automatico che pesca dati reali dalle gare HYROX (tempi, split per stazione, percentili, classifiche) e li trasforma in contenuti per Instagram (post/stories) per fidelizzare gli atleti italiani e differenziarmi dai competitor, che al momento non fanno nulla di simile in modo sistematico.

**Fase attuale (MVP / validazione):** NON vogliamo ancora collegare atleti alle box/palestre (quello sarà uno sviluppo futuro, il vero elemento differenziante). Per ora vogliamo solo:
- Raccogliere automaticamente dati da gare HYROX
- Avere un dataset pulito e aggiornato per costruire contenuti manualmente su Canva
- Validare quali format di contenuto generano più engagement, prima di investire in automazione grafica completa

## Fonte dati: Hyrox Result API (hyroxresultapi.com)

API REST non ufficiale (indipendente, non affiliata a HYROX) ma professionale, versionata, con contratto OpenAPI 3 e documentazione chiara.

- **Base URL:** `https://hyroxresultapi.com/api/v1`
- **Auth:** header `Authorization: Bearer <token>` + `Accept: application/json` su ogni richiesta. Il token si genera da dashboard dopo la sottoscrizione (piano Starter: 30 richieste/minuto, più che sufficiente per il nostro volume).
- **Formato risposta standard:**
```json
{
  "data": { ... },
  "meta": { "data_source": "database" | "live" },
  "errors": null
}
```

### Endpoint principali che ci servono

| Endpoint | Descrizione |
|---|---|
| `GET /seasons` | Lista stagioni HYROX, usare `slug` per filtrare eventi |
| `GET /events` | Lista eventi, filtrabile per stagione/paese/data |
| `GET /events/{slug}` | Dettaglio singolo evento |
| `GET /events/{slug}/divisions` | Divisioni di un evento (id divisione = id evento) |
| `GET /divisions/{id}/results` | Risultati paginati (cursor pagination) di una divisione |
| `GET /athletes/search?q=Cognome&first=Nome` | Ricerca atleta per nome, ritorna race ID e person_ref |
| `GET /athletes/{id}` | Dettaglio gara di un risultato |
| `GET /athletes/{id}/results` | Storico gare di un atleta |
| `GET /athletes/{id}/splits` | Split per stazione (SkiErg, Sled Push/Pull, Row, Wall Balls, ecc.) |
| `GET /stats/divisions/{id}` | Statistiche precalcolate: medie, mediane, deviazione standard, percentili p10-p90, per stazione e tempo finale |
| `GET /simulator/division-benchmarks` | Benchmark globali per divisione (es. `HYROX_MEN`) |

Documentazione completa leggibile anche in plain text via `https://hyroxresultapi.com/llms.txt` (pensata apposta per essere data in pasto a un LLM).

## Cosa deve fare lo script (primo obiettivo concreto)

Uno script Python che:
1. Legge il token API da variabile d'ambiente (mai hardcoded, mai committato)
2. Recupera gli eventi HYROX recenti/rilevanti (Italia + eventi internazionali con atleti italiani)
3. Per ogni evento di interesse, scarica i risultati delle divisioni rilevanti
4. Scarica le statistiche precalcolate (`/stats/divisions/{id}`) per avere subito percentili e medie pronte all'uso
5. Salva tutto in modo pulito e riutilizzabile (CSV e/o JSON) in una cartella `/data`, con nomi file che includano evento e data di sync

Output atteso: dataset pronto da cui poter estrarre a mano (per ora) i dati per costruire card tipo:
- "Record Stazione" (miglior tempo italiano su una stazione)
- "Percentile Check" (un tempo finale con "Top X% in Italia/nel mondo")
- "Testa a testa" (due atleti a confronto sugli stessi split)
- "Weekly Recap" (risultati della settimana + podio)

## Architettura scelta

- **Repo GitHub privato:** `hyrox-content-engine`
- **Automazione:** GitHub Actions con workflow schedulato (es. giornaliero), esegue lo script di sync e salva/commit i nuovi dati
- **Token API:** salvato come GitHub Secret (Settings → Secrets and variables → Actions), MAI nel codice o nei file committati
- **Sviluppo/test locale:** file `.env` locale (escluso via `.gitignore`) durante lo sviluppo con Claude Code

## Sicurezza / cose da NON fare

- Il token API non deve mai finire in chiaro in nessun file che venga committato
- `.gitignore` va creato PRIMA di iniziare a scrivere codice, deve escludere `.env`, secrets, cartelle tipiche Python (`__pycache__`, `venv`, ecc.)
- Il repo resta privato

## Roadmap (per contesto, non da costruire subito)

1. **Fase attuale:** sync dati + contenuti manuali di test (questa sessione)
2. **Fase 2:** se i contenuti funzionano, automatizzare anche la generazione grafica (es. HTML→immagine o Canva API) e la pubblicazione
3. **Fase 3 (futura, NON ORA):** collegare atleti alle box/palestre affiliate IHC, creare classifiche "box vs box", claim del profilo atleta, per creare l'elemento realmente differenziante rispetto a qualsiasi competitor

## Primo task da eseguire ora in Claude Code

1. Inizializzare/collegare il repo git nella cartella corrente al repository GitHub `hyrox-content-engine`
2. Creare il `.gitignore`
3. Creare lo script Python di sync descritto sopra, con struttura chiara e commentata
4. Testare lo script con una chiamata reale (token fornito temporaneamente in locale via `.env`) per verificare che funzioni end-to-end
5. Solo dopo il test positivo, preparare il workflow GitHub Actions (`.github/workflows/sync.yml`) schedulato
