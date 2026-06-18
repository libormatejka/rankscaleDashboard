# Analýza: Rankscale API → BigQuery

**Datum:** 2026-05-21  
**Cíl:** Zmapovat jak napojit Rankscale Metrics API na stávající databázové schéma pro reporting.

---

## Obsah

1. [Shrnutí](#1-shrnutí)
2. [Fundamentální napětí v architektuře](#2-fundamentální-napětí-v-architektuře)
3. [Mapování: API → tabulky](#3-mapování-api--tabulky)
4. [Gap analýza](#4-gap-analýza)
5. [Doporučená architektura ETL](#5-doporučená-architektura-etl)
6. [Schéma změny databáze](#6-schéma-změny-databáze)
7. [Které endpointy volat a jak často](#7-které-endpointy-volat-a-jak-často)
8. [Škálování a kredity](#8-škálování-a-kredity)

---

## 1. Shrnutí

Stávající DB schéma bylo navrženo pro **DIY přístup** – ty sám voláš AI modely, ukládáš raw odpovědi, a metriky si počítáš vlastním kódem. Rankscale je **monitoring SaaS** – prompty spouští za tebe, na více enginech najednou, a vrací předagregované metriky pro všechny detekované brandy zároveň.

Tyto dva přístupy mají jedno klíčové třecí místo: v DB je `brand_id` navázán na `prompts`, což znamená každý prompt sleduje jeden brand. Rankscale ale vrací metriky pro **vlastní brand i všechny konkurenty** z jednoho společného dotazu.

**Doporučení:** Minimální schema změna (`brand_id` přidat na `run_metrics`) + ETL pipeline nad `POST /v1/metrics/search-terms-report` s `includeAnswerTexts: true`. Ostatní endpointy jsou doplňkové nebo nadbytečné.

---

## 2. Fundamentální napětí v architektuře

### Co DB očekává

```
brands ← prompts ← prompt_runs ← run_metrics
   ↑
 brand_id je na PROMPTS
 → každý prompt sleduje jeden brand
```

### Co Rankscale vrací

```
1 search term (query)
   ├── engine: google_ai_overview
   │     ├── ownBrand: {visibilityScore, avgRank, avgSentiment...}
   │     └── competitors[]: [{name, visibilityScore, avgRank...}, ...]
   └── engine: bing_copilot_gui
         ├── ownBrand: {...}
         └── competitors[]: [...]
```

Jedno spuštění Rankscale snapshotu produkuje metriky pro **1 vlastní brand + N konkurentů** najednou.

### Konkrétní příklad konfliktu

Search term „Která banka nabízí nejlepší výhody pro mladé?" vrátí za jeden snapshot:
- Česká spořitelna (vlastní brand): visibility 74, rank 7, sentiment 70
- ČSOB (competitor): visibility 100, rank 1, sentiment 72
- Air Bank (competitor): visibility 77, rank 4, sentiment 78
- …dalších 5 brandů

Ve stávajícím schématu by tento prompt musel mít `brand_id = česká_spořitelna`, a metriky konkurentů by neměly kam jít.

---

## 3. Mapování: API → tabulky

### `brands` – přímé napojení ✅

| Rankscale API | DB sloupec | Transformace |
|---|---|---|
| `GET /v1/metrics/brands` → `data[].brandId` | `brand_id` | přímý přenos |
| `data[].name` | `brand_name` | přímý přenos |
| `data[].isOwnBrand` | `entity_type` | `true` → `OWN_BRAND`, `false` → `COMPETITOR` |
| `data[].website` | `website` | přímý přenos |
| — | `created_at` | `NOW()` při prvním insertu |

Toto je **nejčistší mapování** – 1:1 bez transformací.

### `prompts` – napojení s mezerou ⚠️

| Rankscale API | DB sloupec | Poznámka |
|---|---|---|
| `search-terms[].searchTermId` | `prompt_id` | použij Rankscale ID jako PK |
| `search-terms[].query` | `prompt_text` | přímý přenos |
| `search-terms[].status` | `is_active` | `"active"` → `TRUE` |
| — | `brand_id` | **nutno manuálně** – Rankscale nemá koncept "který brand tento prompt sleduje" |
| — | `product`, `source`, `funnel`, `type` | **nutno manuálně obohatit** – Rankscale tyto dimenze nezná |
| `search-terms[].topic.name` | — | blízké `product`, ale jiná granularita |
| `search-terms[].tags[]` | — | mohlo by mapovat na `source` nebo `segment` |

**Klíčový problém:** Rankscale nezná tvé business dimenze (product, funnel, type). Ty jsou nutné pro reporting. Musí se přiřadit ručně nebo semi-automaticky (např. mapovací tabulka `searchTermId → {product, funnel, type}`).

### `prompt_runs` – napojení s převodem ⚠️

| Rankscale API | DB sloupec | Transformace |
|---|---|---|
| `answerTexts[].executionId` | `run_id` | použij Rankscale execution ID jako PK |
| `searchTermId` | `prompt_id` | FK |
| `answerTexts[].executedAt` | `executed_at` | přímý přenos |
| `answerTexts[].engine` | `ai_model` | Rankscale engine ID = model + provider v jednom (`google_ai_overview`) |
| `answerTexts[].engine` | `ai_provider` | extrahovat prefix: `google_*` → `google`, `bing_*` → `microsoft`, `openai_*` → `openai` |
| `answerTexts[].answerText` | `response_text` | přímý přenos (markdown text) |
| — | `input_tokens` | ❌ Rankscale neposkytuje |
| — | `output_tokens` | ❌ Rankscale neposkytuje |
| — | `prompt_snapshot` | volitelně – zkopírovat `prompt_text` v čase |

> `answerTexts[]` je dostupné pouze pokud zavoláš `search-terms-report` s `includeAnswerTexts: true`. Bez toho `prompt_runs` nelze plnit s texty odpovědí – zbyly by jen agregované metriky bez raw dat.

### `run_metrics` – napojení s rescalováním ⚠️

Toto je nejsložitější část. Rankscale vrací metriky per brand per search term (agregát za období), ne per execution. Výjimkou je timeseries z `/report` endpointu.

**Mapování metrik:**

| Rankscale pole | DB `metric_type` | Transformace hodnoty |
|---|---|---|
| `visibilityScore` (0–100) | `VISIBILITY` | `÷ 100` → 0–1 |
| `avgSentiment` (0–100) | `SENTIMENT` | `(value − 50) ÷ 50` → −1 až +1 |
| `avgRank` (1–N) | `POSITION_RANK` | přímý přenos |
| `detectionRate` (0–100) | `BRAND_MENTION` | `÷ 100` → 0–1 (nebo nový typ `DETECTION_RATE`) |
| — | `RECOMMENDATION` | ❌ Rankscale nemá přímý ekvivalent |

> Sentimentová škála Rankscale je 0–100 kde 50 = neutrální. DB má −1 až +1 kde 0 = neutrální. Transformace: `(rs_sentiment − 50) / 50`.

---

## 4. Gap analýza

### Co schéma zvládne bez změn

- Sync brandů z Rankscale → `brands` ✅
- Sync search termů → `prompts` (s manuálním obohacením) ✅
- Uložení AI odpovědí → `prompt_runs.response_text` ✅
- Metriky vlastního brandu → `run_metrics` s rescalováním ✅

### Co schéma nezvládne bez změny

| Problém | Dopad | Řešení |
|---|---|---|
| `brand_id` je na `prompts`, ne `run_metrics` | Nelze uložit metriky konkurentů – mají jiný brand než prompt | Přidat `brand_id` na `run_metrics` |
| `RECOMMENDATION` metrika nemá Rankscale ekvivalent | Sloupec zůstane prázdný | Buď odstranit, nebo mapovat na `detectionRate >= 80` |
| Token counts (`input_tokens`, `output_tokens`) | Rankscale neposkytuje | Ponechat NULL |
| Metriky jsou agregát za období, ne per-execution | `run_metrics` bude mít duplicitní data pokud se ETL spustí vícekrát | Deduplikace podle `run_id` |
| Citační data nemají tabulku | `POST /v1/metrics/citations` nemá kam jít | Nová tabulka nebo `metric_details` JSON |
| Keyword sentiment nemá tabulku | `positiveKeywords`, `negativeKeywords` jsou bohatá data | `metric_details` JSON na `SENTIMENT` záznamu |

### Co Rankscale nabízí navíc (DB to nezachytí)

| Rankscale data | Popis | Doporučení |
|---|---|---|
| `nameVariations[]` | Různé způsoby jak AI napsal brand | Uložit do `metric_details` |
| `webGroundingKeywords{}` / `trainingDataKeywords{}` | Rozpad klíčových slov dle zdroje AI | Uložit do `metric_details` na `SENTIMENT` metriku |
| `citationsByDomain[]` / `domainSummary` | Které domény AI cituje | Nová tabulka `citations` nebo ignorovat |
| `top3` (% výskytů na pozici 1–3) | Doplňkový rankový ukazatel | Nová `metric_type: TOP3_RATE` nebo do `metric_details` |

---

## 5. Doporučená architektura ETL

### Datový tok

```
Rankscale API
    │
    ▼
ETL skript (Python / Keboola)
    │
    ├── GET /v1/metrics/brands
    │     └──→ UPSERT brands
    │
    ├── GET /v1/metrics/search-terms
    │     └──→ UPSERT prompts (+ manuální metadata)
    │
    ├── POST /v1/metrics/search-terms-report
    │      (includeAnswerTexts: true, timeFrame: 7d)
    │     ├──→ INSERT prompt_runs (answerTexts[])
    │     └──→ INSERT run_metrics (ownBrand + competitors)
    │
    └── POST /v1/metrics/sentiment
          └──→ UPDATE run_metrics[SENTIMENT].metric_details
               (keyword breakdown)

    [volitelně]
    └── POST /v1/metrics/citations
          └──→ INSERT citations (nová tabulka)
```

### Logika pro `run_metrics` – brand per run

Protože Rankscale vrací metriky pro více brandů najednou, jeden prompt_run produkuje **N řádků v run_metrics** (jeden per brand × metric_type):

```
run_id = execution_abc
prompt_id = searchTerm_xyz
   │
   ├── brand_id = ceska_sporitelna → VISIBILITY=0.74, SENTIMENT=0.40, POSITION_RANK=7
   ├── brand_id = csob             → VISIBILITY=1.00, SENTIMENT=0.44, POSITION_RANK=1
   └── brand_id = air_bank         → VISIBILITY=0.77, SENTIMENT=0.56, POSITION_RANK=4
```

### Frekvence ETL

| Krok | Frekvence | Důvod |
|---|---|---|
| Sync `brands` | Týdně | Brandy se přidávají zřídka |
| Sync `prompts` | Týdně | Search termy se mění málo |
| Sync `prompt_runs` + `run_metrics` | Denně | Rankscale snapshoty jsou weekly/daily – denní pull s `7d` window zachytí vše |
| Sync sentiment keywords | Týdně | Bohatá data, mění se pomalu |

**Časové okno pro denní pull:** `timeFrame: 7d` s deduplikací podle `run_id`. Nikdy nestahovat `1y` nebo `3m` dávkově – spotřebuje Rankscale kredity zbytečně.

---

## 6. Schéma změny databáze

### Nezbytná změna: `brand_id` na `run_metrics`

Bez tohoto nelze ukládat metriky konkurentů.

```sql
ALTER TABLE `libor-matejkacz.RankScaleDashboard.run_metrics`
ADD COLUMN brand_id STRING;

-- Poznámka: BigQuery ALTER TABLE ADD COLUMN je backward-compatible,
-- existující řádky dostanou NULL.
```

Po přidání: `brand_id` bude NULL pro stávající záznamy (vlastní brand se dá doplnit z prompts.brand_id přes JOIN), a nové záznamy z Rankscale budou mít brand_id vyplněné.

### Doporučená doplňková změna: nové `metric_type` hodnoty

```sql
-- Přidat do referenčních hodnot:
-- DETECTION_RATE  → 0.0–1.0   (detectionRate / 100)
-- TOP3_RATE       → 0.0–1.0   (top3 / 100)
-- VISIBILITY_SCORE → 0.0–1.0  (alias pro VISIBILITY z Rankscale)
```

### Volitelná nová tabulka: `citations`

Pokud chceš reporting nad citacemi (domény, URL), přidej:

```sql
CREATE TABLE `libor-matejkacz.RankScaleDashboard.citations` (
  citation_id  STRING    NOT NULL,
  brand_id     STRING    NOT NULL,
  domain       STRING    NOT NULL,
  url          STRING,
  occurrences  INT64     NOT NULL,
  engine_id    STRING,
  fetched_at   TIMESTAMP NOT NULL,
  period_start TIMESTAMP NOT NULL,
  period_end   TIMESTAMP NOT NULL
)
PARTITION BY DATE(fetched_at)
CLUSTER BY brand_id, domain
```

---

## 7. Které endpointy volat a jak často

### Primární (nutné pro základní reporting)

| Endpoint | Kdy volat | Co naplní |
|---|---|---|
| `GET /v1/metrics/brands` | Týdně | `brands` tabulka |
| `GET /v1/metrics/search-terms` | Týdně | `prompts` tabulka |
| `POST /v1/metrics/search-terms-report` (`includeAnswerTexts: true`) | Denně | `prompt_runs` + `run_metrics` |

### Doplňkové (obohacení dat)

| Endpoint | Kdy volat | Co přidá |
|---|---|---|
| `POST /v1/metrics/sentiment` | Týdně | Keyword breakdown do `metric_details` na SENTIMENT řádcích |
| `POST /v1/metrics/citations` | Týdně | Citační data (nová tabulka nebo ignorovat) |

### Nepotřebné pro ETL

| Endpoint | Proč přeskočit |
|---|---|
| `POST /v1/metrics/report` | Vrací timeseries (hourly/daily/weekly buckets) – duplicitní data k search-terms-report, ale v jiném formátu. Vhodné pro granulární historii, ne pro základní ETL. |
| `GET /v1/metrics/credits` | Monitoring, ne data. Volej jen pro alerting na vyčerpání kreditů. |
| `GET /v1/metrics/topics` | Konfigurační data Rankscale workspace – nepotřebné pro reporting. |

---

## 8. Škálování a kredity

### Odhad spotřeby kreditů

Rankscale spotřebovává kredity per API call (ne per search term). Základní denní ETL:
- 1× `GET /brands` = 1 kredit
- 1× `GET /search-terms` = 1 kredit  
- 1× `POST /search-terms-report` (s `answerTexts`) = 1 kredit (vše najednou)
- **Celkem: ~3 kredity/den pro základní ETL**

Týdenní s obohacením:
- +1× `POST /sentiment`
- +1× `POST /citations`
- **Celkem: ~5 kreditů navíc za týden**

### Idempotence a deduplikace

ETL musí být idempotentní – opakované spuštění nesmí duplikovat data.

```sql
-- Vždy MERGE nebo INSERT IF NOT EXISTS místo prostého INSERT:
MERGE `prompt_runs` AS target
USING (SELECT @run_id AS run_id, ...) AS source
ON target.run_id = source.run_id
WHEN NOT MATCHED THEN INSERT (...)
```

BigQuery podporuje `MERGE` nativně. Alternativně: staging tabulka → deduplikace → produkce.

### Historická data

Rankscale uchovává historii dle plánu (Agency/Enterprise). ETL by měl při prvním spuštění stáhnout `timeFrame: 1y` pro inicializaci, pak přejít na inkrementální `7d`.

---

## Závěr: prioritizace

| Priorita | Akce |
|---|---|
| 🔴 P0 | Přidat `brand_id` na `run_metrics` (bez toho nejde uložit data konkurentů) |
| 🔴 P0 | Napsat ETL pro `search-terms-report` s `includeAnswerTexts: true` |
| 🟠 P1 | Manuálně obohatit `prompts` o business dimenze (`product`, `funnel`, `type`) pro každý search term |
| 🟠 P1 | Sync `brands` z Rankscale do DB |
| 🟡 P2 | Týdenní ETL pro `sentiment` (keyword breakdown do `metric_details`) |
| 🟡 P2 | Rozhodnout co dělat s citacemi – nová tabulka nebo ignorovat |
| 🟢 P3 | Alerting na kredity (`GET /credits`) |
