# Rankscale → BigQuery ETL – Kontext projektu

## Co projekt dělá

Denní ETL pipeline: Rankscale Metrics API → Google BigQuery.
Spouští se automaticky každý den v 6:00 UTC přes GitHub Actions.

---

## Aktuální stav (funkční pipeline)

- ETL skript: `src/rankscale_etl.py` — 4 kroky, funkční
- BigQuery dataset: `libor-matejkacz.RankScaleDashboard`
- GitHub Actions: `.github/workflows/etl.yml` — cron 6:00 UTC
- GitHub Secrets: `RANKSCALE_API_KEY`, `GCP_PROJECT`, `BQ_DATASET`, `GCP_SA_JSON` — vše nastaveno

---

## 4 tabulky v BigQuery

| Tabulka | Zdroj | Strategie |
|---|---|---|
| `dim_brands` | `GET /v1/metrics/brands` | TRUNCATE |
| `dim_search_terms` | `GET /v1/metrics/search-terms` | TRUNCATE |
| `fact_brand_snapshots` | `POST /v1/metrics/search-terms-report` | PARTITION OVERWRITE |
| `fact_answer_texts` | `POST /v1/metrics/search-terms-report` (includeAnswerTexts: true) | APPEND + dedup |

Detailní popis tabulek: `docs/bigquery-data-model.md`

---

## Dokumentace

| Soubor | Obsah |
|---|---|
| `docs/bigquery-data-model.md` | Schema tabulek, sloupce, SQL příklady |
| `docs/rankscale-endpoints.md` | Všechny API endpointy, parametry, reálné response struktury |
| `docs/apiResponses/` | Ukázky reálných JSON odpovědí z API |
| `sql/schema_rankscale.sql` | DDL pro vytvoření tabulek v BigQuery |
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

## Brand ID

`E5GAVmqco65u7Smx3hso` — Česká spořitelna workspace

---

## Zastaralé schéma (ignoruj)

`docs/outdated/` obsahuje starý návrh (brands → prompts → prompt_runs → run_metrics).
Nikdy nebyl implementován — ETL ho nepoužívá.
