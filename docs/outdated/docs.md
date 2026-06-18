# RankscaleMetrics – Dokumentace tabulek

**Dataset:** `libor-matejkacz.RankscaleMetrics`
**Zdroj dat:** Rankscale Metrics API (https://rankscale.ai/v1/metrics/)
**Aktualizace:** denně v 6:00 UTC přes GitHub Actions

---

## Obsah

1. [dim_brands](#1-dim_brands)
2. [dim_search_terms](#2-dim_search_terms)
3. [fact_report_timeseries](#3-fact_report_timeseries)
4. [fact_report_by_engine](#4-fact_report_by_engine)
5. [fact_search_term_snapshots](#5-fact_search_term_snapshots)
6. [fact_answer_texts](#6-fact_answer_texts)
7. [fact_sentiment_timeseries](#7-fact_sentiment_timeseries)
8. [fact_sentiment_by_engine](#8-fact_sentiment_by_engine)
9. [fact_citations](#9-fact_citations)

---

## 1. dim_brands

**Endpoint:** `GET /v1/metrics/brands`
**Zápis:** `WRITE_TRUNCATE` – celá tabulka se nahrazuje při každém runu
**Velikost:** malá (jednotky řádků – jeden řádek per brand v Rankscale workspace)

### Popis
Obsahuje seznam brandů sledovaných v Rankscale workspace. Slouží jako hlavní dimenze pro join s fact tabulkami. Pokud sleduješ i konkurenci, každý konkurent je samostatný záznam.

### Schéma

| Sloupec | Typ | Povinný | Popis |
|---|---|---|---|
| `brand_id` | STRING | ✅ | Unikátní ID brandy z Rankscale API (`data.brands[].id`) |
| `name` | STRING | ✅ | Zobrazovaný název brandy |
| `domain` | STRING | | Hlavní doména, např. `collectorboy.cz` |
| `variants` | JSON | | Alternativní názvy brandy, např. `["CollectorBoy", "Collector Boy"]` |
| `search_term_count` | INT64 | | Počet aktivních search terms pro tuto brandy |
| `created_at` | TIMESTAMP | | Kdy byla branda přidána do Rankscale |
| `loaded_at` | TIMESTAMP | ✅ | Kdy byl záznam načten do BQ |

### Příklad záznamu
```json
{
  "brand_id": "E5GAVmqco65u7Smx3hso",
  "name": "CollectorBoy.cz",
  "domain": "collectorboy.cz",
  "variants": "[\"CollectorBoy\", \"Collector Boy\"]",
  "search_term_count": 456,
  "created_at": "2024-06-15T10:00:00Z",
  "loaded_at": "2026-04-27T06:01:00Z"
}
```

### Typický dotaz
```sql
-- Přehled brandů
SELECT brand_id, name, domain, search_term_count
FROM `libor-matejkacz.RankscaleMetrics.dim_brands`
ORDER BY name;
```

---

## 2. dim_search_terms

**Endpoint:** `GET /v1/metrics/search-terms?brandId=ID`
**Zápis:** `WRITE_TRUNCATE` – celá tabulka se nahrazuje při každém runu
**Velikost:** střední (stovky řádků – jeden per search term)

### Popis
Obsahuje seznam všech search terms (promptů / klíčových dotazů) které jsou sledovány v Rankscale pro danou brandy. Search term je konkrétní dotaz zadávaný do AI enginů, např. _„kde koupit Hot Toys figury v ČR"_. Tabulka slouží jako dimenze pro rozpad fact dat podle tématu nebo tagu.

### Schéma

| Sloupec | Typ | Povinný | Popis |
|---|---|---|---|
| `search_term_id` | STRING | ✅ | Unikátní ID search termu z API |
| `brand_id` | STRING | ✅ | FK → `dim_brands.brand_id` |
| `query` | STRING | ✅ | Přesné znění promptu zadávaného do AI |
| `topic` | STRING | | Název tematické skupiny (string, ne ID), např. `"Hot Toys"` |
| `tags` | JSON | | Pole štítků, např. `["funnel:top", "market:cz"]` |
| `engines` | JSON | | Enginy na kterých se prompt spouští, např. `["chatgpt", "perplexity"]` |
| `interval` | STRING | | Frekvence spouštění: `"daily"`, `"hourly"` |
| `region` | STRING | | Geografický region: `"us"`, `"de"`, `"cz"` |
| `active` | BOOL | | Zda je search term aktivní |
| `created_at` | TIMESTAMP | | Kdy byl search term přidán do Rankscale |
| `loaded_at` | TIMESTAMP | ✅ | Kdy byl záznam načten do BQ |

### Poznámky
- `topic` je prostý string – API nevrací topic ID. Pokud potřebuješ groupovat, seskupuj přímo podle hodnoty `topic`.
- `tags` a `engines` jsou uloženy jako JSON string – pro dotazy je rozbal pomocí `JSON_QUERY_ARRAY()`.
- Sloupec `` `interval` `` je v DDL obalený backticky protože `INTERVAL` je rezervované slovo v BigQuery.

### Příklad záznamu
```json
{
  "search_term_id": "st_abc123",
  "brand_id": "E5GAVmqco65u7Smx3hso",
  "query": "kde koupit Hot Toys figury v ČR",
  "topic": "Hot Toys",
  "tags": "[\"funnel:top\", \"market:cz\"]",
  "engines": "[\"chatgpt\", \"perplexity\", \"gemini\"]",
  "interval": "daily",
  "region": "cz",
  "active": true,
  "created_at": "2024-07-01T08:00:00Z",
  "loaded_at": "2026-04-27T06:01:30Z"
}
```

### Typické dotazy
```sql
-- Počet search terms per topic
SELECT topic, COUNT(*) AS term_count
FROM `libor-matejkacz.RankscaleMetrics.dim_search_terms`
WHERE active = TRUE
GROUP BY topic
ORDER BY term_count DESC;

-- Rozbal tagy z JSON
SELECT search_term_id, query, tag
FROM `libor-matejkacz.RankscaleMetrics.dim_search_terms`,
  UNNEST(JSON_VALUE_ARRAY(tags)) AS tag
WHERE active = TRUE;
```

---

## 3. fact_report_timeseries

**Endpoint:** `POST /v1/metrics/report` → `data.timeSeries[]`
**Zápis:** partition overwrite per `date` – přepíše jen dotčené dny
**Partition:** `DATE(date)`
**Cluster:** `brand_id`
**Velikost:** roste denně (jeden řádek per brand per den)

### Popis
Hlavní časová řada visibility metrik agregovaná přes všechny search terms a enginy. Jeden řádek = jeden den pro jeden brand. Tato tabulka je základem pro trendové grafy a přehledové dashboardy. Hodnoty jsou průměry/součty za daný den přes všechny aktivní search terms.

### Schéma

| Sloupec | Typ | Povinný | Popis |
|---|---|---|---|
| `date` | DATE | ✅ | Datum (partition key) |
| `brand_id` | STRING | ✅ | FK → `dim_brands.brand_id` |
| `aggregation_level` | STRING | ✅ | Úroveň agregace: `"daily"`, `"weekly"`, `"monthly"` |
| `visibility` | FLOAT64 | | Průměrné visibility skóre za den (škála 0–100) |
| `position` | FLOAT64 | | Průměrná pozice brandy v AI odpovědích |
| `sentiment` | FLOAT64 | | Průměrný sentiment (float **0–1**, ne procento!) |
| `mentions` | INT64 | | Celkový počet zmínek brandy v AI odpovědích |
| `detection_rate` | FLOAT64 | | % promptů kde se branda objevila (0–100) |
| `citations` | INT64 | | Počet citací webu brandy jako zdroje |
| `top3_pct` | FLOAT64 | | % výskytů kde byla branda v top 3 (0–100) |
| `loaded_at` | TIMESTAMP | ✅ | Kdy byl záznam načten do BQ |

### Poznámky
- `sentiment` je **float 0–1** (např. `0.72`), nikoli procento ani string. Pro zobrazení v % násob 100.
- `visibility` je na škále 0–100 (proprietary Rankscale metrika).
- ETL táhne vždy posledních `7d` – data se překrývají, partition overwrite zajistí že nejsou duplikáty.

### Typické dotazy
```sql
-- 30denní trend visibility
SELECT date, visibility, mentions, detection_rate, top3_pct
FROM `libor-matejkacz.RankscaleMetrics.fact_report_timeseries`
WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND brand_id = 'E5GAVmqco65u7Smx3hso'
  AND aggregation_level = 'daily'
ORDER BY date;

-- Klouzavý 7denní průměr visibility
SELECT
  date,
  visibility,
  AVG(visibility) OVER (
    ORDER BY date
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  ) AS visibility_7d_ma
FROM `libor-matejkacz.RankscaleMetrics.fact_report_timeseries`
WHERE brand_id = 'E5GAVmqco65u7Smx3hso'
  AND aggregation_level = 'daily'
ORDER BY date;
```

---

## 4. fact_report_by_engine

**Endpoint:** `POST /v1/metrics/report` → `data.byEngine{}`
**Zápis:** partition overwrite per `snapshot_date`
**Partition:** `DATE(snapshot_date)`
**Cluster:** `brand_id`, `engine_name`
**Velikost:** roste denně (jeden řádek per brand per engine per den)

### Popis
Breakdown visibility metrik podle AI enginu. Jeden řádek = jeden engine pro jeden brand v den kdy byl API call proveden. Data jsou agregátem za celý sledovaný `timeFrame` (ne per den) – proto `snapshot_date` označuje kdy byl snapshot pořízen, ne datum dat samotných.

### Schéma

| Sloupec | Typ | Povinný | Popis |
|---|---|---|---|
| `snapshot_date` | DATE | ✅ | Datum API callu – partition key |
| `brand_id` | STRING | ✅ | FK → `dim_brands.brand_id` |
| `engine_name` | STRING | ✅ | Název AI enginu, např. `"chatgpt"`, `"perplexity"`, `"gemini"` |
| `time_frame` | STRING | | Časové okno za které jsou data agregována, např. `"7d"` |
| `visibility` | FLOAT64 | | Visibility skóre pro tento engine (0–100) |
| `position` | FLOAT64 | | Průměrná pozice na tomto enginu |
| `mentions` | INT64 | | Počet zmínek na tomto enginu za sledované období |
| `loaded_at` | TIMESTAMP | ✅ | Kdy byl záznam načten do BQ |

### Typické dotazy
```sql
-- Porovnání enginů – aktuální snapshot
SELECT engine_name, visibility, position, mentions
FROM `libor-matejkacz.RankscaleMetrics.fact_report_by_engine`
WHERE snapshot_date = CURRENT_DATE()
  AND brand_id = 'E5GAVmqco65u7Smx3hso'
ORDER BY visibility DESC;

-- Trend per engine za posledních 30 dní
SELECT snapshot_date, engine_name, visibility
FROM `libor-matejkacz.RankscaleMetrics.fact_report_by_engine`
WHERE snapshot_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND brand_id = 'E5GAVmqco65u7Smx3hso'
ORDER BY snapshot_date, engine_name;
```

---

## 5. fact_search_term_snapshots

**Endpoint:** `POST /v1/metrics/search-terms-report` → `data.searchTerms[]`
**Zápis:** partition overwrite per `snapshot_date`
**Partition:** `DATE(snapshot_date)`
**Cluster:** `brand_id`, `search_term_id`
**Velikost:** roste denně (jeden řádek per search term per den – při 456 termech ≈ 456 řádků/den)

### Popis
Denní snapshot metrik pro každý jednotlivý search term. Umožňuje vidět které konkrétní prompty fungují dobře a které špatně. Obsahuje i trendová data (change + direction) oproti předchozímu období. Tato tabulka je klíčová pro analýzu na úrovni jednotlivých dotazů – kde přesně branda vede a kde zaostává.

### Schéma

| Sloupec | Typ | Povinný | Popis |
|---|---|---|---|
| `snapshot_date` | DATE | ✅ | Datum snapshottu – partition key |
| `search_term_id` | STRING | ✅ | FK → `dim_search_terms.search_term_id` |
| `brand_id` | STRING | ✅ | FK → `dim_brands.brand_id` |
| `query` | STRING | | Znění promptu (denormalizováno pro snadný reporting) |
| `topic` | STRING | | Téma (denormalizováno) |
| `tags` | JSON | | Tagy (denormalizováno) |
| `latest_run_date` | TIMESTAMP | | Kdy byl naposledy spuštěn tento prompt |
| `visibility` | FLOAT64 | | Visibility skóre pro tento term (0–100) |
| `position` | FLOAT64 | | Průměrná pozice brandy v odpovědích na tento prompt |
| `sentiment` | FLOAT64 | | Sentiment (0–1) |
| `mentions` | INT64 | | Počet zmínek |
| `citations` | INT64 | | Počet citací |
| `engines_detail` | JSON | | Breakdown per engine: `{"chatgpt": {"visibility": 70, "position": 1}}` |
| `trend_visibility_change` | FLOAT64 | | Změna visibility oproti předchozímu období (kladné = zlepšení) |
| `trend_visibility_dir` | STRING | | Směr trendu: `"up"` nebo `"down"` |
| `trend_position_change` | FLOAT64 | | Změna pozice |
| `trend_position_dir` | STRING | | Směr trendu pozice: `"improved"` nebo `"declined"` |
| `loaded_at` | TIMESTAMP | ✅ | Kdy byl záznam načten do BQ |

### Typické dotazy
```sql
-- Top 10 search terms dle visibility (dnešní snapshot)
SELECT query, topic, visibility, position, mentions, trend_visibility_dir
FROM `libor-matejkacz.RankscaleMetrics.fact_search_term_snapshots`
WHERE snapshot_date = CURRENT_DATE()
  AND brand_id = 'E5GAVmqco65u7Smx3hso'
ORDER BY visibility DESC
LIMIT 10;

-- Search terms s nejlepším trendem
SELECT query, visibility, trend_visibility_change, trend_visibility_dir
FROM `libor-matejkacz.RankscaleMetrics.fact_search_term_snapshots`
WHERE snapshot_date = CURRENT_DATE()
  AND trend_visibility_dir = 'up'
ORDER BY trend_visibility_change DESC;

-- Breakdown per topic
SELECT topic, AVG(visibility) AS avg_visibility, COUNT(*) AS term_count
FROM `libor-matejkacz.RankscaleMetrics.fact_search_term_snapshots`
WHERE snapshot_date = CURRENT_DATE()
GROUP BY topic
ORDER BY avg_visibility DESC;
```

---

## 6. fact_answer_texts

**Endpoint:** `POST /v1/metrics/search-terms-report` s `includeAnswerTexts: true` → `data.searchTerms[].answerTexts[]`
**Zápis:** append + dedup na `execution_id` – každý execution se zapíše právě jednou
**Partition:** `DATE(executed_at)`
**Cluster:** `brand_id`, `engine_name`
**Velikost:** velká a roste rychle (jeden řádek per každý reálný AI response)

### Popis
Raw texty odpovědí AI enginů na jednotlivé search terms. Každý řádek je jedna skutečná odpověď konkrétního enginu na konkrétní prompt v konkrétní čas. Tabulka je zdrojem pro kvalitativní analýzu – co přesně AI o brandě říká, jak ji popisuje, v jakém kontextu ji zmiňuje.

### Schéma

| Sloupec | Typ | Povinný | Popis |
|---|---|---|---|
| `execution_id` | STRING | ✅ | Unikátní ID jednoho spuštění promptu na enginu (dedup klíč) |
| `search_term_id` | STRING | ✅ | FK → `dim_search_terms.search_term_id` |
| `brand_id` | STRING | ✅ | FK → `dim_brands.brand_id` |
| `query` | STRING | | Znění promptu (denormalizováno) |
| `executed_at` | TIMESTAMP | | Kdy byl prompt spuštěn na AI enginu – partition key |
| `engine_name` | STRING | | Název enginu: `"perplexity_gui"`, `"chatgpt_gui"` apod. |
| `answer_text` | STRING | | Plný text odpovědi AI enginu (může být stovky slov) |
| `loaded_at` | TIMESTAMP | ✅ | Kdy byl záznam načten do BQ |

### Poznámky
- Tabulka může být objemná – 456 search terms × 3 enginy × denní spouštění = stovky řádků denně.
- `answer_text` může mít stovky až tisíce znaků per řádek – počítej s tím při odhadech úložiště.
- Dedup na `execution_id` zajišťuje že stejná odpověď není uložena dvakrát i když ETL táhne překrývající se časová okna.
- Tuto tabulku načítej jen pokud raw texty skutečně potřebuješ – `includeAnswerTexts: true` zpomaluje API volání.

### Typické dotazy
```sql
-- Poslední odpovědi pro konkrétní search term
SELECT executed_at, engine_name, answer_text
FROM `libor-matejkacz.RankscaleMetrics.fact_answer_texts`
WHERE search_term_id = 'st_abc123'
ORDER BY executed_at DESC
LIMIT 10;

-- Počet odpovědí per engine za posledních 7 dní
SELECT engine_name, COUNT(*) AS response_count
FROM `libor-matejkacz.RankscaleMetrics.fact_answer_texts`
WHERE executed_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND brand_id = 'E5GAVmqco65u7Smx3hso'
GROUP BY engine_name;
```

---

## 7. fact_sentiment_timeseries

**Endpoint:** `POST /v1/metrics/sentiment` → `data.timeSeries[]`
**Zápis:** partition overwrite per `date`
**Partition:** `DATE(date)`
**Cluster:** `brand_id`
**Velikost:** roste denně (jeden řádek per brand per den)

### Popis
Denní časová řada sentimentu – jak pozitivně/negativně AI enginy celkově hovoří o brandě. Sentiment score je float 0–1 kde vyšší hodnota = pozitivnější. Distribuce (positive/neutral/negative) ukazuje podíl jednotlivých kategorií.

### Schéma

| Sloupec | Typ | Povinný | Popis |
|---|---|---|---|
| `date` | DATE | ✅ | Datum – partition key |
| `brand_id` | STRING | ✅ | FK → `dim_brands.brand_id` |
| `sentiment_score` | FLOAT64 | | Celkový sentiment score (**float 0–1**, ne procento) |
| `positive_pct` | FLOAT64 | | Podíl pozitivních zmínek (0–1, např. `0.65` = 65 %) |
| `neutral_pct` | FLOAT64 | | Podíl neutrálních zmínek (0–1) |
| `negative_pct` | FLOAT64 | | Podíl negativních zmínek (0–1) |
| `loaded_at` | TIMESTAMP | ✅ | Kdy byl záznam načten do BQ |

### Poznámky
- **Všechny hodnoty jsou 0–1**, ne procenta. Pro zobrazení v % násob 100.
- `positive_pct + neutral_pct + negative_pct` by mělo dát přibližně 1.0.
- Sentiment score není prostý průměr distribuce – je to vlastní Rankscale metrika.

### Typické dotazy
```sql
-- Trend sentimentu za 30 dní
SELECT
  date,
  ROUND(sentiment_score * 100, 1) AS sentiment_pct,
  ROUND(positive_pct * 100, 1) AS positive_pct,
  ROUND(neutral_pct * 100, 1) AS neutral_pct,
  ROUND(negative_pct * 100, 1) AS negative_pct
FROM `libor-matejkacz.RankscaleMetrics.fact_sentiment_timeseries`
WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND brand_id = 'E5GAVmqco65u7Smx3hso'
ORDER BY date;
```

---

## 8. fact_sentiment_by_engine

**Endpoint:** `POST /v1/metrics/sentiment` → `data.byEngine{}`
**Zápis:** partition overwrite per `snapshot_date`
**Partition:** `DATE(snapshot_date)`
**Cluster:** `brand_id`, `engine_name`
**Velikost:** roste denně (jeden řádek per brand per engine per den)

### Popis
Sentiment rozpadnutý podle AI enginu – na kterém enginu mluví AI o brandě nejpozitivněji. Jeden řádek = jeden engine v den kdy byl snapshot pořízen. Data jsou agregátem za celý sledovaný `timeFrame`.

### Schéma

| Sloupec | Typ | Povinný | Popis |
|---|---|---|---|
| `snapshot_date` | DATE | ✅ | Datum snapshottu – partition key |
| `brand_id` | STRING | ✅ | FK → `dim_brands.brand_id` |
| `engine_name` | STRING | ✅ | Název enginu: `"chatgpt"`, `"gemini"`, `"perplexity"` |
| `sentiment_score` | FLOAT64 | | Sentiment score pro tento engine (0–1) |
| `sentiment_label` | STRING | | Textový label: `"positive"`, `"neutral"`, `"negative"` |
| `loaded_at` | TIMESTAMP | ✅ | Kdy byl záznam načten do BQ |

### Typické dotazy
```sql
-- Porovnání sentimentu per engine (dnešní snapshot)
SELECT engine_name, ROUND(sentiment_score * 100, 1) AS sentiment_pct, sentiment_label
FROM `libor-matejkacz.RankscaleMetrics.fact_sentiment_by_engine`
WHERE snapshot_date = CURRENT_DATE()
  AND brand_id = 'E5GAVmqco65u7Smx3hso'
ORDER BY sentiment_score DESC;
```

---

## 9. fact_citations

**Endpoint:** `POST /v1/metrics/citations` → `data.citations[]`
**Zápis:** partition overwrite per `last_seen`
**Partition:** `DATE(last_seen)`
**Cluster:** `brand_id`, `domain`
**Velikost:** střední (stovky až tisíce řádků – jedna citace per URL per engine per search term)

### Popis
Záznamy o URL a doménách které AI enginy citují jako zdroje při odpovídání na sledované search terms. Ukazuje kdo je citován místo (nebo společně s) tvou brandou. Klíčová tabulka pro analýzu konkurenční citovanosti – které weby jsou AI enginy považovány za autoritativní zdroje pro tvá témata.

### Schéma

| Sloupec | Typ | Povinný | Popis |
|---|---|---|---|
| `search_term_id` | STRING | ✅ | FK → `dim_search_terms.search_term_id` |
| `brand_id` | STRING | ✅ | FK → `dim_brands.brand_id` |
| `engine_name` | STRING | ✅ | Engine kde se citace objevila |
| `url` | STRING | ✅ | Citovaná URL (součást přirozeného klíče) |
| `title` | STRING | | Titulek citované stránky |
| `domain` | STRING | | Doména citované stránky, např. `"example.com"` |
| `query` | STRING | | Znění search termu (denormalizováno) |
| `first_seen` | TIMESTAMP | | Kdy byla citace poprvé zaznamenána |
| `last_seen` | TIMESTAMP | | Kdy byla citace naposledy viděna – partition key |
| `citation_count` | INT64 | | Celkový počet výskytů této citace |
| `loaded_at` | TIMESTAMP | ✅ | Kdy byl záznam načten do BQ |

### Poznámky
- Přirozený klíč je trojice `(search_term_id, engine_name, url)` – API průběžně aktualizuje `last_seen` a `citation_count` u existujících citací.
- API podporuje stránkování (`hasMore` + `offset`) – ETL automaticky stránkuje dokud nenačte vše.
- Tato tabulka odpovídá na otázku: _„Které weby citují AI enginy když někdo hledá témata relevantní pro moji brandy?"_

### Typické dotazy
```sql
-- Top citované domény za posledních 30 dní
SELECT domain, SUM(citation_count) AS total_citations, COUNT(DISTINCT url) AS unique_urls
FROM `libor-matejkacz.RankscaleMetrics.fact_citations`
WHERE last_seen >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
  AND brand_id = 'E5GAVmqco65u7Smx3hso'
GROUP BY domain
ORDER BY total_citations DESC
LIMIT 20;

-- Které domény jsou citovány pro konkrétní topic
SELECT c.domain, c.url, c.citation_count, c.engine_name
FROM `libor-matejkacz.RankscaleMetrics.fact_citations` c
JOIN `libor-matejkacz.RankscaleMetrics.dim_search_terms` s
  ON c.search_term_id = s.search_term_id
WHERE s.topic = 'Hot Toys'
  AND c.brand_id = 'E5GAVmqco65u7Smx3hso'
ORDER BY c.citation_count DESC;

-- Citace per engine – kde jsem nejvíce citován
SELECT engine_name, COUNT(DISTINCT url) AS unique_urls, SUM(citation_count) AS total
FROM `libor-matejkacz.RankscaleMetrics.fact_citations`
WHERE brand_id = 'E5GAVmqco65u7Smx3hso'
  AND domain = 'collectorboy.cz'
GROUP BY engine_name
ORDER BY total DESC;
```

---

## Vztahy mezi tabulkami

```
dim_brands
  └── brand_id → fact_report_timeseries.brand_id
  └── brand_id → fact_report_by_engine.brand_id
  └── brand_id → fact_sentiment_timeseries.brand_id
  └── brand_id → fact_sentiment_by_engine.brand_id
  └── brand_id → fact_search_term_snapshots.brand_id
  └── brand_id → fact_answer_texts.brand_id
  └── brand_id → fact_citations.brand_id

dim_search_terms
  └── search_term_id → fact_search_term_snapshots.search_term_id
  └── search_term_id → fact_answer_texts.search_term_id
  └── search_term_id → fact_citations.search_term_id
```

---

## Zápis dat – přehled strategií

| Tabulka | Strategie | Důvod |
|---|---|---|
| `dim_brands` | WRITE_TRUNCATE | Malá tabulka, celá se nahrazuje |
| `dim_search_terms` | WRITE_TRUNCATE | Malá tabulka, celá se nahrazuje |
| `fact_report_timeseries` | Partition overwrite per `date` | Přepíše jen dotčené dny |
| `fact_report_by_engine` | Partition overwrite per `snapshot_date` | Přepíše jen dnešní snapshot |
| `fact_search_term_snapshots` | Partition overwrite per `snapshot_date` | Přepíše jen dnešní snapshot |
| `fact_answer_texts` | Append + dedup na `execution_id` | Raw data, jednou zapsat navždy |
| `fact_sentiment_timeseries` | Partition overwrite per `date` | Přepíše jen dotčené dny |
| `fact_sentiment_by_engine` | Partition overwrite per `snapshot_date` | Přepíše jen dnešní snapshot |
| `fact_citations` | Partition overwrite per `last_seen` | API průběžně aktualizuje count |

> **Proč load jobs místo streaming inserts?**
> BQ streaming insert (`insert_rows_json`) plní interní "streaming buffer".
> Dokud se buffer nevyprázdní (může trvat hodiny), nelze na daných řádcích
> dělat DELETE ani partition overwrite. Load jobs zapisují přímo do table
> storage – žádný buffer, žádné omezení.