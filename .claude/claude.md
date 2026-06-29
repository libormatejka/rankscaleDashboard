# Rankscale → BigQuery – Kontext projektu

## Co projekt dělá

Denní pipeline: Rankscale Metrics API → Google BigQuery → Keboola → Snowflake → Tableau.
BigQuery je L0 raw landing zone — žádné transformace, data jsou 1:1 z API.

---

## Aktuální stav

- **Aktivní script:** `src/rankscale_extract.py` — čistý EL, žádná transformační logika
- **Archivní script:** `src/rankscale_etl.py` — starší verze s transformacemi v Pythonu, zachována
- BigQuery dataset: `libor-matejkacz.RankScaleDashboard`
- **Aktivní workflow:** `.github/workflows/extract.yml` — cron 6:30 UTC
- Archivní workflow: `.github/workflows/etl.yml` — cron 6:00 UTC
- GitHub Secrets: `RANKSCALE_API_KEY`, `GCP_PROJECT`, `BQ_DATASET`, `GCP_SA_JSON` — vše nastaveno

---

## Proč dva skripty

`rankscale_extract.py` dělá pouze EL — stáhne data z API a APPENDuje je 1:1 do `raw_*` tabulek. Žádná transformační logika. Transformace (dedup, is_active, SCD, joiny) patří do Kebooly.

`rankscale_etl.py` dělal transformace přímo v Pythonu (UPSERT/MERGE, is_active flagy, partition overwrite). Zachován jako archiv, není aktivně udržován.

---

## Raw tabulky v BigQuery (aktivní)

| Tabulka | Zdroj | Strategie |
|---|---|---|
| `raw_brands` | `GET /v1/metrics/brands` | APPEND |
| `raw_search_terms` | `GET /v1/metrics/search-terms` | APPEND |
| `raw_brand_snapshots` | `POST /v1/metrics/search-terms-report` | APPEND |
| `raw_answer_texts` | `POST /v1/metrics/search-terms-report` (includeAnswerTexts: true) | APPEND |
| `raw_citations` | `POST /v1/metrics/citations` | APPEND |

DDL: `sql/schema_raw.sql`

---

## Dokumentace

| Soubor | Obsah |
|---|---|
| `docs/bigquery-data-model.md` | Schema tabulek, diagram závislostí, SQL příklady |
| `docs/etl-flow.md` | Celý průběh pipeline krok za krokem |
| `docs/etl-loading-strategy.md` | Strategie zápisu dat (APPEND, proč ne MERGE) |
| `docs/rankscale-endpoints.md` | Všechny API endpointy, parametry, reálné response struktury |
| `docs/apiResponses/` | Ukázky reálných JSON odpovědí z API |
| `sql/schema_raw.sql` | DDL pro raw_ tabulky |
| `sql/schema_rankscale.sql` | DDL pro starší transformované tabulky (archiv) |
| `docs/outdated/` | Staré návrhy a analýzy — ignorovat |

---

## Klíčová zjištění (reálné API vs. dokumentace)

- Pole `term` (ne `query`) v search-terms response
- `searchTermTopicRef` je objekt `{ id, name }` (ne string)
- `status: "active"` (ne boolean `active`)
- `aiSearchEngines[]` — vždy jen jeden engine per záznam
- Sentiment škála: 0–100 (ne 0–1)
- Detailní odchylky: `docs/rankscale-endpoints.md`

---

## Brand IDs

- `E5GAVmqco65u7Smx3hso` — Česká spořitelna workspace
- `tkek4nJAg1lrRbyhjqlM` — druhý brand (1500+ search termů)
