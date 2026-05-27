# BigQuery Data Model — AI Visibility Dashboard

## Přehled architektury

```
Rankscale API
    ↓
GitHub Actions (Python ETL)   – src/rankscale_etl.py
    ↓
BigQuery (L0 staging)         – tato vrstva, schema viz sql/schema_rankscale.sql
    ↓
Keboola (transformace L0→L1)
    ↓
Snowflake (reporting)         – finální schema viz sql/keboolaSchema.sql
    ↓
Tableau
```

BigQuery je **L0 staging layer** — data jsou Rankscale-nativní, bez transformací.
Při změně nástroje se změní ETL a BQ schema, Snowflake reporting schema zůstane.

---

## Tabulky

### 1. `dim_brands` — číselník brandů

**Zdroj:** `GET /v1/metrics/brands`  
**Load strategie:** WRITE_TRUNCATE (celá tabulka se přepíše při každém runu)  
**Velikost:** malá (1–5 řádků, jen vlastní brandy)

| Sloupec | Typ | Popis |
|---|---|---|
| `brand_id` | STRING | Rankscale brand ID |
| `name` | STRING | Název brandu |
| `domain` | STRING | Doména (z pole `url` v API) |
| `is_own_brand` | BOOL | Vždy TRUE — endpoint vrací jen vlastní brandy |
| `search_term_count` | INT64 | Počet aktivních search termů |
| `loaded_at` | TIMESTAMP | Čas ETL runu |

> Competitors **nejsou** v této tabulce — Rankscale je nevrací jako samostatné brandy.
> Jejich `brand_name` je dostupný přímo v `fact_brand_snapshots`.

---

### 2. `dim_search_terms` — číselník dotazů

**Zdroj:** `GET /v1/metrics/search-terms`  
**Load strategie:** WRITE_TRUNCATE (celá tabulka se přepíše při každém runu)  
**Velikost:** střední (~456 řádků = unikátní kombinace dotaz × engine)

| Sloupec | Typ | Popis |
|---|---|---|
| `search_term_id` | STRING | Rankscale ID (unikátní per dotaz × engine) |
| `brand_id` | STRING | FK → dim_brands |
| `query` | STRING | Text dotazu posílaného AI enginu (pole `term` v API) |
| `topic_id` | STRING | Rankscale topic ID |
| `topic_name` | STRING | `Brand` / `Půjčky/Úvěry` / `Investice` |
| `engine` | STRING | `google_ai_mode_gui` / `chatgpt_gui` / ... |
| `region` | STRING | `cz` / `sk` / ... |
| `interval` | STRING | `weekly` |
| `tags` | JSON | Pole tagů z Rankscale |
| `is_active` | BOOL | TRUE = aktivní search term |
| `loaded_at` | TIMESTAMP | Čas ETL runu |

---

### 3. `fact_brand_snapshots` — metriky ← HLAVNÍ TABULKA

**Zdroj:** `POST /v1/metrics/search-terms-report` (includeAnswerTexts: false)  
**Load strategie:** PARTITION OVERWRITE per `snapshot_date` (přepíše jen dotčený týden)  
**Velikost:** roste ~2 300 řádků/týden (433 search termů × vlastní brand + competitors)  
**Partition:** `snapshot_date` (DATE)  
**Cluster:** `is_own_brand`, `topic_name`, `engine`

Jeden řádek = **brand × search term × týdenní snapshot**.

| Sloupec | Typ | Popis |
|---|---|---|
| `snapshot_date` | DATE | Datum snapshotu (= partition key) |
| `snapshot_week` | STRING | ISO týden, např. `2026-21` |
| `search_term_id` | STRING | FK → dim_search_terms |
| `brand_name` | STRING | Název brandu (vlastní i competitor) |
| `is_own_brand` | BOOL | TRUE = vlastní brand, FALSE = competitor |
| `brand_id` | STRING | FK → dim_brands (NULL pro nesledované competitors) |
| `visibility_score` | FLOAT64 | 0–100; prominentnost zmínky v AI odpovědích |
| `avg_sentiment` | FLOAT64 | 0–100; 50 = neutrální, >50 pozitivní |
| `avg_rank` | FLOAT64 | Průměrná pozice v AI odpovědi (1 = nejlepší); NULL = nedetekován |
| `latest_rank` | INT64 | Rank v posledním snapshotu |
| `detection_rate` | FLOAT64 | 0–100 %; % snapshotů kde byl brand detekován |
| `top3_rate` | FLOAT64 | 0–100 %; % výskytů na pozici 1–3 |
| `citation_count` | INT64 | Počet URL citací tohoto brandu |
| `appearances` | INT64 | Počet snapshotů kde se brand objevil |
| `query` | STRING | Text dotazu (denorm. bez JOIN) |
| `topic_name` | STRING | `Brand` / `Půjčky/Úvěry` / `Investice` (denorm.) |
| `engine` | STRING | AI engine (denorm.) |
| `last_snapshot_at` | TIMESTAMP | Kdy proběhl poslední Rankscale snapshot |
| `loaded_at` | TIMESTAMP | Čas ETL runu |

**Důležité:** Metriky jsou **předagregované Rankscale** za dané `timeFrame` (defaultně 7d).
Nejedná se o raw data jednotlivých execucí — to jsou `fact_answer_texts`.

---

### 4. `fact_answer_texts` — raw AI odpovědi

**Zdroj:** `POST /v1/metrics/search-terms-report` (includeAnswerTexts: true)  
**Load strategie:** APPEND + dedup podle `execution_id` (každá exekuce se uloží jen jednou)  
**Velikost:** roste ~250 řádků/týden; velká tabulka v dlouhodobém horizontu  
**Partition:** `executed_at` (TIMESTAMP → DATE)  
**Cluster:** `engine`

Jeden řádek = **jedna AI odpověď na jeden dotaz** (raw text).

| Sloupec | Typ | Popis |
|---|---|---|
| `execution_id` | STRING | Unikátní ID exekuce (dedup key) |
| `search_term_id` | STRING | FK → dim_search_terms |
| `executed_at` | TIMESTAMP | Kdy AI engine odpověděl |
| `engine` | STRING | AI engine |
| `query` | STRING | Text dotazu |
| `topic_name` | STRING | Téma |
| `answer_text` | STRING | Plný markdown text AI odpovědi |
| `loaded_at` | TIMESTAMP | Čas ETL runu |

**K čemu slouží:** Audit obsahu AI odpovědí, NLP analýzy, vlastní výpočet metrik.
Pro standardní dashboard reporting používej `fact_brand_snapshots`.

---

## Kdy použít kterou tabulku

| Potřebuji | Tabulka |
|---|---|
| Visibility score, rank, sentiment mého brandu | `fact_brand_snapshots` WHERE is_own_brand = TRUE |
| Srovnání s konkurencí | `fact_brand_snapshots` (všechny řádky) |
| Trend v čase (po týdnech) | `fact_brand_snapshots` GROUP BY snapshot_week |
| Jaké dotazy sledujeme a na jakých enginech | `dim_search_terms` |
| Co přesně AI o nás napsal | `fact_answer_texts` |
| Kolik search termů máme aktivních | `dim_search_terms` WHERE is_active = TRUE |

---

## Příklady SQL

```sql
-- Vývoj visibility vlastního brandu po týdnech
SELECT
  snapshot_week,
  engine,
  AVG(visibility_score) AS avg_visibility,
  AVG(avg_rank)         AS avg_rank,
  AVG(detection_rate)   AS avg_detection
FROM `libor-matejkacz.RankScaleDashboard.fact_brand_snapshots`
WHERE is_own_brand = TRUE
GROUP BY snapshot_week, engine
ORDER BY snapshot_week;

-- Top 10 competitors podle visibility (aktuální týden)
SELECT
  brand_name,
  AVG(visibility_score) AS avg_visibility,
  AVG(detection_rate)   AS avg_detection
FROM `libor-matejkacz.RankScaleDashboard.fact_brand_snapshots`
WHERE is_own_brand = FALSE
  AND snapshot_week = FORMAT_DATE('%G-%V', CURRENT_DATE())
GROUP BY brand_name
ORDER BY avg_visibility DESC
LIMIT 10;

-- Freshness check — kdy byl poslední snapshot
SELECT
  MAX(last_snapshot_at) AS last_snapshot,
  MAX(loaded_at)        AS last_etl_run
FROM `libor-matejkacz.RankScaleDashboard.fact_brand_snapshots`;
```
