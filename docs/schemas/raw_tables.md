# Raw tabulky — L0 landing zone

Surová data stažená 1:1 z Rankscale API. Žádná transformační logika.
Plněno scriptem `src/rankscale_extract.py`.

---

## Přehled

```
Rankscale API
     │
     ├── GET  /v1/metrics/brands               → raw_brands
     ├── GET  /v1/metrics/search-terms         → raw_search_terms
     ├── POST /v1/metrics/search-terms-report  → raw_brand_snapshots
     ├── POST /v1/metrics/search-terms-report  → raw_answer_texts   (includeAnswerTexts: true)
     └── POST /v1/metrics/citations            → raw_citations
```

| Tabulka | Grain | Strategice zápisu |
|---|---|---|
| `raw_brands` | 1 řádek per brand per ETL run | APPEND |
| `raw_search_terms` | 1 řádek per prompt × engine per brand per ETL run | APPEND |
| `raw_brand_snapshots` | 1 řádek per brand (vlastní + competitor) per prompt per ETL run | APPEND |
| `raw_answer_texts` | 1 řádek per AI exekuce per ETL run | APPEND |
| `raw_citations` | 1 řádek per URL × engine × prompt per ETL run | APPEND |

**Každý ETL run přidá nové řádky — historická data zůstávají.**
Deduplikaci a čistění zajišťují L1 transformace (`transform_l1.sql`).

---

## raw_brands

**Zdroj:** `GET /v1/metrics/brands`
**Grain:** 1 řádek per brand per ETL run

Seznam vlastních brandů monitorovaných v Rankscale workspace. Competitors zde nejsou — ti se objevují v `raw_brand_snapshots`.

| Sloupec | Typ | API pole | Popis |
|---|---|---|---|
| `brand_id` | STRING | `brands[].id` | Unikátní ID brandu — klíč pro ostatní endpointy |
| `name` | STRING | `brands[].name` | Název brandu |
| `domain` | STRING | `brands[].url` | Hlavní URL brandu |
| `is_own_brand` | BOOL | — | Vždy `TRUE` — brands endpoint vrací jen vlastní brandy |
| `etl_loaded_at` | TIMESTAMP | — | Kdy byl řádek stažen (přidává script) |

---

## raw_search_terms

**Zdroj:** `GET /v1/metrics/search-terms?brandId=...&limit=5000`
**Grain:** 1 řádek per prompt × engine per brand per ETL run

Aktuální seznam sledovaných promptů. Jeden prompt běžící na 3 enginech = 3 řádky.
Neobsahuje metriky — jen konfiguraci promptu.

| Sloupec | Typ | API pole | Popis |
|---|---|---|---|
| `brand_id` | STRING | z parametru volání | Čí brand tento prompt patří |
| `search_term_id` | STRING | `searchTerms[].id` | Unikátní ID záznamu (prompt × engine) |
| `query` | STRING | `searchTerms[].term` | Text promptu posílaného do AI enginu |
| `engine` | STRING | `searchTerms[].aiSearchEngines[0]` | AI engine (`chatgpt_gui`, `perplexity_gui`...) |
| `topic_id` | STRING | `searchTerms[].searchTermTopicRef.id` | ID produktové vertikály |
| `topic_name` | STRING | `searchTerms[].searchTermTopicRef.name` | Název vertikály (Půjčky, Hypotéky...) |
| `region` | STRING | `searchTerms[].region` | Geografický region (`cz`, `sk`...) |
| `interval` | STRING | `searchTerms[].interval` | Frekvence spouštění (`weekly`, `daily`) |
| `tags` | STRING | `searchTerms[].tags` | JSON string štítků, např. `'["product-brand","top-funnel"]'` |
| `status` | STRING | `searchTerms[].status` | `"active"` nebo `"inactive"` |
| `created_at` | TIMESTAMP | `searchTerms[].createdAt` | Kdy byl prompt v Rankscale založen |
| `last_execution_time` | TIMESTAMP | `searchTerms[].lastExecutionTime` | Kdy byl prompt naposledy spuštěn |
| `next_execution_time` | TIMESTAMP | `searchTerms[].nextScheduledExecutionTime` | Kdy bude spuštěn příště |
| `executions_amount` | INT64 | `searchTerms[].executionsAmount` | Celkový počet spuštění (roste každým runem) |
| `etl_loaded_at` | TIMESTAMP | — | Kdy byl řádek stažen |

> `executions_amount` se aktualizuje každým ETL runem — L1 dedup vezme vždy nejnovější hodnotu.

---

## raw_brand_snapshots

**Zdroj:** `POST /v1/metrics/search-terms-report` (`includeAnswerTexts: false`)
**Grain:** 1 řádek per brand (vlastní + každý competitor) per prompt per ETL run

Hlavní tabulka metrik. Pro každý prompt obsahuje řádek pro vlastní brand a řádek pro každého detekovaného competitora v AI odpovědích.

| Sloupec | Typ | API pole | Popis |
|---|---|---|---|
| `brand_id` | STRING | z parametru volání | Čí brand monitoring tento záznam patří |
| `search_term_id` | STRING | `searchTerms[].searchTermId` | ID promptu |
| `engine` | STRING | `searchTerms[].aiSearchEngines[0]` | AI engine |
| `topic_id` | STRING | `searchTerms[].topic.id` | Topic platný v době snapshotu |
| `topic_name` | STRING | `searchTerms[].topic.name` | Název topicu v době snapshotu |
| `last_snapshot_at` | TIMESTAMP | `searchTerms[].lastSnapshotAt` | Kdy Rankscale provedl snapshot → základ pro `snapshot_week` v L1 |
| `brand_name` | STRING | `ownBrand.name` / `competitors[].name` | Název brandu nebo competitora |
| `is_own_brand` | BOOL | `isOwnBrand` | `TRUE` = vlastní brand, `FALSE` = competitor |
| `visibility_score` | FLOAT64 | `visibilityScore` | 0–100; jak prominentně AI brand zmiňuje |
| `avg_sentiment` | FLOAT64 | `avgSentiment` | 0–100; 50 = neutrální, >50 = pozitivní |
| `avg_rank` | FLOAT64 | `avgRank` | Průměrná pozice v AI odpovědi za dané období (1 = nejlepší) |
| `latest_rank` | INT64 | `latestRank` | Pozice v posledním konkrétním snapshotu (`NULL` = nenalezen) |
| `detection_rate` | FLOAT64 | `detectionRate` | % snapshotů kde byl brand detekován (0–100) |
| `top3_rate` | FLOAT64 | `top3` | % výskytů na pozici 1–3 (0–100) |
| `citation_count` | INT64 | `citationCount` | Počet citovaných URL |
| `appearances` | INT64 | `appearances` | Počet snapshotů kde se brand v daném období objevil |
| `etl_loaded_at` | TIMESTAMP | — | Kdy byl řádek stažen |

> Pro backfill se volá s `periodOffset` — každý offset = jiný týden, jiné `last_snapshot_at`.

---

## raw_answer_texts

**Zdroj:** `POST /v1/metrics/search-terms-report` (`includeAnswerTexts: true`)
**Grain:** 1 řádek per AI exekuce per ETL run

Plné texty AI odpovědí. Jeden prompt může mít více odpovědí — jedna per spuštění (`execution_id`).
`execution_id` je přirozený unikátní klíč — L1 dedup podle něj eliminuje duplicity z opakovaných runů.

| Sloupec | Typ | API pole | Popis |
|---|---|---|---|
| `brand_id` | STRING | z parametru volání | Čí brand monitoring odpověď zachytil |
| `search_term_id` | STRING | `searchTerms[].searchTermId` | ID promptu |
| `execution_id` | STRING | `answerTexts[].executionId` | Unikátní ID konkrétní AI exekuce |
| `executed_at` | TIMESTAMP | `answerTexts[].executedAt` | Kdy AI engine odpověděl |
| `engine` | STRING | `answerTexts[].engine` | Který AI engine odpovídal |
| `answer_text` | STRING | `answerTexts[].answerText` | Plný text AI odpovědi (markdown) |
| `etl_loaded_at` | TIMESTAMP | — | Kdy byl řádek stažen |

---

## raw_citations

**Zdroj:** `POST /v1/metrics/citations` → `domainSummary.topDomainsByQuery`
**Grain:** 1 řádek per URL × engine × prompt per ETL run

Weby citované AI enginy v odpovědích na sledované prompty.

| Sloupec | Typ | API pole | Popis |
|---|---|---|---|
| `brand_id` | STRING | z parametru volání | Čí brand monitoring citaci zachytil |
| `search_term_id` | STRING | `searchTermIds[0]` | ID promptu |
| `query` | STRING | `query` | Text promptu |
| `engine` | STRING | `engines[].engineId` | AI engine který citaci použil |
| `domain` | STRING | `domains[].domain` | Citovaná doména, např. `banky.cz` |
| `url` | STRING | `urls[].url` | Konkrétní citovaná URL (`NULL` pokud API URL nevrátilo) |
| `occurrences` | INT64 | `urls[].occurrences` | Počet výskytů v daném období |
| `etl_loaded_at` | TIMESTAMP | — | Kdy byl řádek stažen |

> Citations nemají vlastní timestamp — `etl_loaded_at` je jediný časový údaj. Pro historii se vždy stahuje jen aktuální týden.

---

## DDL

```sql
sql/schema_raw.sql
```

Pro přidání nového sloupce do existující tabulky:
```sql
ALTER TABLE `libor-matejkacz.RankScaleDashboard.raw_search_terms`
ADD COLUMN created_at TIMESTAMP;
```
