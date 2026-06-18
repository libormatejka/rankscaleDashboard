# BigQuery – aktuální schéma

**Projekt:** `libor-matejkacz`  
**Dataset:** `RankScaleDashboard`  
**ETL skript:** `src/rankscale_etl.py`  
**Detailní dokumentace:** `docs/bigquery-data-model.md`

---

## 4 tabulky plněné ETL skriptem

| Tabulka | Zdroj (API) | Strategie | Popis |
|---|---|---|---|
| `dim_brands` | `GET /v1/metrics/brands` | TRUNCATE | Číselník vlastních brandů |
| `dim_search_terms` | `GET /v1/metrics/search-terms` | TRUNCATE | Číselník dotazů (query × engine) |
| `fact_brand_snapshots` | `POST /v1/metrics/search-terms-report` | PARTITION OVERWRITE | Metriky per brand per search term per týden — **hlavní tabulka** |
| `fact_answer_texts` | `POST /v1/metrics/search-terms-report` (includeAnswerTexts: true) | APPEND + dedup | Raw texty AI odpovědí |

---

## Klíčové poznámky

- `dim_brands` obsahuje **jen vlastní brandy** — competitors jsou jen v `fact_brand_snapshots` (sloupec `brand_name`, `is_own_brand = FALSE`)
- `fact_brand_snapshots` — jeden řádek = brand × search term × týdenní snapshot
- `fact_answer_texts` — dedup podle `execution_id`, každá exekuce se zapíše jednou navždy
- Metriky jsou škálované 0–100 (Rankscale nativní), **nerescalované**
- Kroky 3 a 4 (fact tabulky) se přeskočí pokud Rankscale nemá novější data než BQ (freshness check)

---

## Zastaralé schéma (ignoruj)

Soubory v `docs/outdated/` popisují starý návrh (brands → prompts → prompt_runs → run_metrics + EAV metriky).
Tento model **nikdy nebyl implementován** — aktuální ETL ho nepoužívá.
