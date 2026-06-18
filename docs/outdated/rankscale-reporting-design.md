# Rankscale Reporting – Návrh architektury

**Datum:** 2026-05-21

---

## Obsah

1. [Co máme k dispozici](#1-co-máme-k-dispozici)
2. [Klíčová zjištění z dat](#2-klíčová-zjištění-z-dat)
3. [Navrhované schéma databáze](#3-navrhované-schéma-databáze)
4. [ETL pipeline](#4-etl-pipeline)
5. [Reportingové dotazy](#5-reportingové-dotazy)
6. [Co tento návrh neumí](#6-co-tento-návrh-neumí)

---

## 1. Co máme k dispozici

### Data z Rankscale (reálná čísla z API)

| Dimenze | Počet |
|---|---|
| Unikátní query texty (prompty) | **75** |
| Témata (topics) | **3** – Brand, Půjčky/Úvěry, Investice |
| AI enginy | **6** – google_ai_mode_gui, google_ai_overview, chatgpt_gui, google_gemini_gui, bing_copilot_gui, perplexity_gui |
| SearchTermIds celkem (query × engine) | **433** |
| Frekvence snapshotů | **weekly** |
| Vlastní brand nenalezen (ze 433) | **190 termů** – brand nebyl detekován v žádném snapshotu |

### Metriky dostupné per brand per search term

| Metrika | Rankscale pole | Rozsah |
|---|---|---|
| Visibility | `visibilityScore` | 27–100 (vlastní brand) |
| Sentiment | `avgSentiment` | 35–100 (vlastní brand) |
| Pozice | `avgRank` | 1–10 (vlastní brand) |
| Detection rate | `detectionRate` | 0–100 % |
| Top-3 rate | `top3` | 0–100 % |
| Počet citací | `citationCount` | 0–N |

---

## 2. Klíčová zjištění z dat

### `searchTermId` = query × engine, ne query samotná

Jeden query text „Jaká je nejlepší banka pro hypotéku?" existuje v Rankscale jako **5–6 různých searchTermId** – jedno pro každý engine. V DB musíme prompty ukládat na úrovni **query textu** (75 řádků), nikoliv na úrovni searchTermId (433 řádků). Engine jde na `prompt_runs`.

```
prompts        (75 řádků)  – jeden per unikátní query text
  └─ prompt_runs  (433+ řádků) – jeden per query × engine × týden
       └─ run_metrics  (N řádků)  – jeden per brand × metrika × run
```

### 190 termů bez vlastního brandu = normální stav

Brand nebyl detekován AI v žádném snapshotu daného search termu a enginu. Tyto řádky v `prompt_runs` existují (run proběhl), ale v `run_metrics` pro vlastní brand **chybí**. Konkurenti tam ale být mohou.

### Competitors jsou dynamičtí – nejsou fixní seznam

Rankscale detekuje competitors organicky z AI odpovědí. Přichází variace názvů: `MONETA`, `Moneta Money Bank`, `MONETA Money Bank` jsou tři různé záznamy pro jeden brand. Při ukládání musíš normalizovat přes `variations[]`.

---

## 3. Navrhované schéma databáze

### Přehled změn vs. stávající schéma

| Tabulka | Akce | Co se mění |
|---|---|---|
| `brands` | ✅ beze změny | Přibydou řádky z Rankscale |
| `topics` | 🆕 nová tabulka | Rankscale topics (Brand, Půjčky/Úvěry…) |
| `prompts` | ✏️ rozšíření | Přidat `topic_id`, `engine_id`, `region`, `rs_search_term_id` |
| `prompt_runs` | ✏️ rozšíření | Přidat `engine_id`, `week_start` |
| `run_metrics` | ✏️ rozšíření | Přidat `brand_id`, `brand_name`, `is_own_brand` |

### `topics` – nová tabulka

```sql
CREATE TABLE `libor-matejkacz.RankScaleDashboard.topics` (
  topic_id   STRING    NOT NULL,  -- Rankscale topic ID
  topic_name STRING    NOT NULL,  -- "Brand", "Půjčky/Úvěry", "Investice"
  brand_id   STRING    NOT NULL,  -- FK → brands.brand_id (vlastní brand)
  created_at TIMESTAMP NOT NULL
)
```

Plní se z `GET /v1/metrics/topics`.

### `prompts` – úpravy

```sql
ALTER TABLE `libor-matejkacz.RankScaleDashboard.prompts`
  ADD COLUMN topic_id         STRING,   -- FK → topics.topic_id
  ADD COLUMN engine_id        STRING,   -- "google_ai_mode_gui" atd.
  ADD COLUMN region           STRING,   -- "cz", "sk" atd.
  ADD COLUMN rs_search_term_id STRING;  -- Rankscale searchTermId (jeden per query×engine)
```

> Stávající `product`, `funnel`, `type` sloupce zůstávají – mapuješ je manuálně na topic nebo je naplníš automaticky dle témat (Brand → `product=brand`, Půjčky/Úvěry → `product=loan` atd.).

**Výsledná struktura prompt_id:**
Používej Rankscale `searchTermId` přímo jako `prompt_id`. 433 řádků = 433 prompt records, každý pro jednu kombinaci query × engine.

Pokud chceš 75 řádků (query text), přidej spojovací tabulku `prompt_engines` – viz sekce 6.

### `prompt_runs` – úpravy

```sql
ALTER TABLE `libor-matejkacz.RankScaleDashboard.prompt_runs`
  ADD COLUMN engine_id  STRING,    -- "google_ai_mode_gui" (redundantní s prompt, ale praktické)
  ADD COLUMN week_start TIMESTAMP; -- začátek týdne (pondělí), pro time-series
```

**Jak generovat `run_id`:**
```
run_id = searchTermId + "_" + YYYY-WW
-- např. "zr9vMtv0MBbtng8KTglh_2026-21"
```

Každý týden ETL přidá nový řádek per searchTerm → time series funguje automaticky.

### `run_metrics` – úpravy (nejdůležitější)

```sql
ALTER TABLE `libor-matejkacz.RankScaleDashboard.run_metrics`
  ADD COLUMN brand_id      STRING,   -- FK → brands.brand_id (NULL pokud brand není v číselníku)
  ADD COLUMN brand_name    STRING,   -- denormalizovaný název (včetně neznámých brandů)
  ADD COLUMN is_own_brand  BOOL;     -- true = vlastní brand, false = competitor
```

**Nové `metric_type` hodnoty:**

| Hodnota | Rozsah | Zdroj |
|---|---|---|
| `VISIBILITY` | 0.0–1.0 | `visibilityScore / 100` |
| `SENTIMENT` | -1.0–1.0 | `(avgSentiment - 50) / 50` |
| `POSITION_RANK` | 1–N | `avgRank` přímý přenos |
| `DETECTION_RATE` | 0.0–1.0 | `detectionRate / 100` |
| `TOP3_RATE` | 0.0–1.0 | `top3 / 100` |
| `CITATION_COUNT` | 0–N | `citationCount` přímý přenos |

> `RECOMMENDATION` z původního schématu v Rankscale nemá přímý ekvivalent. Nejbližší je `DETECTION_RATE ≥ 0.8` nebo `TOP3_RATE`. Doporučuji `DETECTION_RATE` jako náhradu.

### ERD po změnách

```
┌──────────┐       ┌──────────────┐
│  brands  │◄──────│   topics     │
│──────────│       │──────────────│
│ brand_id │       │ topic_id  PK │
│ ...      │       │ topic_name   │
└──────────┘       │ brand_id  FK │
     ▲             └──────────────┘
     │                    ▲
     │             ┌──────┴───────────┐
     │             │     prompts      │
     │             │──────────────────│
     │             │ prompt_id    PK  │ ← searchTermId
     │             │ prompt_text      │ ← query
     │             │ brand_id     FK  │ ← vlastní brand
     │             │ topic_id     FK  │ ← nové
     │             │ engine_id        │ ← nové
     │             │ region           │ ← nové
     │             │ rs_search_term_id│ ← nové
     │             │ product, funnel  │ ← manuální obohacení
     │             │ type, source     │
     │             └──────────────────┘
     │                    ▲
     │             ┌──────┴───────────────┐
     │             │     prompt_runs      │
     │             │──────────────────────│
     │             │ run_id           PK  │ ← searchTermId_YYYY-WW
     │             │ prompt_id        FK  │
     │             │ executed_at          │ ← lastSnapshotAt
     │             │ week_start           │ ← nové
     │             │ engine_id            │ ← nové
     │             │ ai_model             │ ← engine
     │             │ response_text        │ ← answerText (volitelné)
     │             └──────────────────────┘
     │                    ▲
     └──────────┐  ┌──────┴───────────────┐
                │  │     run_metrics      │
                │  │──────────────────────│
                └──│ brand_id         FK  │ ← nové
                   │ brand_name           │ ← nové (denorm.)
                   │ is_own_brand         │ ← nové
                   │ run_id           FK  │
                   │ metric_type          │
                   │ metric_value         │
                   │ metric_details  JSON │ ← keyword data ze sentiment endpointu
                   └──────────────────────┘
```

---

## 4. ETL pipeline

### Frekvence a pořadí kroků

```
Každý týden (např. pondělí ráno, po Rankscale snapshotu):

1. GET /v1/metrics/brands          → UPSERT brands
2. GET /v1/metrics/topics          → UPSERT topics
3. GET /v1/metrics/search-terms    → UPSERT prompts
4. POST /v1/metrics/search-terms-report
   (timeFrame: 7d, includeAnswerTexts: true)
   → INSERT prompt_runs (idempotentně)
   → INSERT run_metrics (idempotentně)

Jednou měsíčně:
5. POST /v1/metrics/sentiment      → UPDATE run_metrics[SENTIMENT].metric_details
                                     (keyword breakdown)

Volitelně:
6. POST /v1/metrics/citations      → INSERT citations (pokud přidáš tabulku)
```

### Pseudokód ETL – hlavní krok (krok 4)

```python
def etl_search_terms_report(brand_id, week_start):
    week_label = week_start.strftime("%Y-%W")
    
    response = rankscale.post("/v1/metrics/search-terms-report", {
        "brandId": brand_id,
        "timeFrame": "7d",
        "includeAnswerTexts": True
    })
    
    for term in response["data"]["searchTerms"]:
        search_term_id = term["searchTermId"]
        engine = term["aiSearchEngines"][0]
        run_id = f"{search_term_id}_{week_label}"
        
        # --- prompt_runs ---
        answer_text = None
        if term.get("answerTexts"):
            answer_text = term["answerTexts"][0]["answerText"]
        
        upsert("prompt_runs", {
            "run_id": run_id,
            "prompt_id": search_term_id,   # prompt_id = searchTermId
            "executed_at": term["lastSnapshotAt"],
            "week_start": week_start,
            "engine_id": engine,
            "ai_model": engine,
            "ai_provider": engine.split("_")[0],  # "google", "bing", "openai"...
            "response_text": answer_text
        })
        
        # --- run_metrics – pro každý brand v search termu ---
        brands_in_term = []
        
        if "ownBrand" in term:
            brands_in_term.append({**term["ownBrand"], "is_own_brand": True})
        
        for competitor in term.get("competitors", []):
            brands_in_term.append({**competitor, "is_own_brand": False})
        
        for brand_data in brands_in_term:
            brand_name = brand_data["name"]
            is_own = brand_data["is_own_brand"]
            
            metrics = {
                "VISIBILITY":       brand_data["visibilityScore"] / 100,
                "SENTIMENT":        (brand_data["avgSentiment"] - 50) / 50,
                "POSITION_RANK":    brand_data["avgRank"],
                "DETECTION_RATE":   brand_data["detectionRate"] / 100,
                "TOP3_RATE":        brand_data["top3"] / 100,
                "CITATION_COUNT":   brand_data["citationCount"],
            }
            
            for metric_type, value in metrics.items():
                if value is None:
                    continue  # avgRank může být None pokud brand nenalezen
                
                insert_idempotent("run_metrics", {
                    "metric_id":    f"{run_id}_{brand_name}_{metric_type}",
                    "run_id":       run_id,
                    "brand_name":   brand_name,
                    "is_own_brand": is_own,
                    "metric_type":  metric_type,
                    "metric_value": value,
                    "computed_at":  week_start
                })
```

### Normalizace konkurentů (name variations)

Rankscale detekuje stejný brand různými názvy. Mapovací tabulka:

```python
COMPETITOR_NORMALIZATION = {
    "MONETA": "MONETA Money Bank",
    "Moneta": "MONETA Money Bank",
    "Moneta Money Bank": "MONETA Money Bank",
    "MONETA Bank": "MONETA Money Bank",
    "KB": "Komerční banka",
    "Komerční banky": "Komerční banka",
    "UniCredit": "UniCredit Bank",
    "airbank": "Air Bank",
    "mbank": "mBank",
    "ČS": "Česká spořitelna",
    "Spořitelna": "Česká spořitelna",
}

def normalize_brand_name(name):
    return COMPETITOR_NORMALIZATION.get(name, name)
```

Aplikuj normalizaci před uložením do `brand_name`. Pro `brand_id` lookupni z `brands` tabulky po normalizaci – pokud brand není v číselníku, nech `brand_id = NULL` (brand byl detekován AI ale není sledovaný v Rankscale).

### Manuální obohacení `prompts`

Rankscale nezná tvé business dimenze. Po prvním syncu promptů je musíš obohatit:

```sql
-- Automatické mapování dle topicu (dobrý výchozí bod)
UPDATE prompts SET
  product = CASE topic_id
    WHEN 'ZFyMrgG0cuuEAvCdf1nr' THEN 'brand'    -- topic "Brand"
    WHEN 'loan_topic_id'         THEN 'loan'     -- topic "Půjčky/Úvěry"
    WHEN 'invest_topic_id'       THEN 'invest'   -- topic "Investice"
  END,
  source  = 'Custom',   -- nebo importuj z tagů v Rankscale
  funnel  = 'Think',    -- výchozí; uprav dle obsahu promptu
  type    = 'inform'    -- výchozí; uprav dle záměru
WHERE source IS NULL;

-- Pak projdi ručně a zpřesni funnel/type pro každý prompt
```

---

## 5. Reportingové dotazy

Po naplnění dat jsou dostupné tyto typy reportů:

### Seznam promptů dle topicu

```sql
SELECT
  t.topic_name,
  p.prompt_text,
  p.engine_id,
  COUNT(DISTINCT r.run_id)                                             AS weeks_tracked,
  ROUND(AVG(IF(m.metric_type='VISIBILITY' AND m.is_own_brand, m.metric_value, NULL)), 2) AS avg_visibility,
  ROUND(AVG(IF(m.metric_type='POSITION_RANK' AND m.is_own_brand, m.metric_value, NULL)), 1) AS avg_rank
FROM `libor-matejkacz.RankScaleDashboard.prompts`       p
JOIN `libor-matejkacz.RankScaleDashboard.topics`        t  ON p.topic_id  = t.topic_id
JOIN `libor-matejkacz.RankScaleDashboard.prompt_runs`   r  ON r.prompt_id = p.prompt_id
JOIN `libor-matejkacz.RankScaleDashboard.run_metrics`   m  ON m.run_id    = r.run_id
GROUP BY t.topic_name, p.prompt_text, p.engine_id
ORDER BY t.topic_name, avg_visibility DESC;
```

### Vlastní brand vs. konkurence (per topic)

```sql
SELECT
  t.topic_name,
  m.brand_name,
  m.is_own_brand,
  ROUND(AVG(IF(m.metric_type='VISIBILITY',    m.metric_value, NULL)), 3) AS avg_visibility,
  ROUND(AVG(IF(m.metric_type='SENTIMENT',     m.metric_value, NULL)), 3) AS avg_sentiment,
  ROUND(AVG(IF(m.metric_type='POSITION_RANK', m.metric_value, NULL)), 1) AS avg_rank,
  ROUND(AVG(IF(m.metric_type='DETECTION_RATE',m.metric_value, NULL)), 3) AS avg_detection,
  SUM(IF(m.metric_type='CITATION_COUNT', m.metric_value, NULL))          AS total_citations
FROM `libor-matejkacz.RankScaleDashboard.run_metrics`   m
JOIN `libor-matejkacz.RankScaleDashboard.prompt_runs`   r ON m.run_id    = r.run_id
JOIN `libor-matejkacz.RankScaleDashboard.prompts`       p ON r.prompt_id = p.prompt_id
JOIN `libor-matejkacz.RankScaleDashboard.topics`        t ON p.topic_id  = t.topic_id
GROUP BY t.topic_name, m.brand_name, m.is_own_brand
ORDER BY t.topic_name, avg_visibility DESC;
```

### Vývoj v čase – vlastní brand vs. top competitor

```sql
SELECT
  DATE_TRUNC(r.week_start, WEEK)                                      AS week,
  t.topic_name,
  m.brand_name,
  m.is_own_brand,
  ROUND(AVG(IF(m.metric_type='VISIBILITY',    m.metric_value, NULL)), 3) AS avg_visibility,
  ROUND(AVG(IF(m.metric_type='SENTIMENT',     m.metric_value, NULL)), 3) AS avg_sentiment,
  ROUND(AVG(IF(m.metric_type='POSITION_RANK', m.metric_value, NULL)), 1) AS avg_rank
FROM `libor-matejkacz.RankScaleDashboard.run_metrics`   m
JOIN `libor-matejkacz.RankScaleDashboard.prompt_runs`   r ON m.run_id    = r.run_id
JOIN `libor-matejkacz.RankScaleDashboard.prompts`       p ON r.prompt_id = p.prompt_id
JOIN `libor-matejkacz.RankScaleDashboard.topics`        t ON p.topic_id  = t.topic_id
WHERE m.is_own_brand = TRUE
   OR m.brand_name IN ('ČSOB', 'Komerční banka', 'Air Bank')   -- top 3 sledovaní competitors
GROUP BY week, t.topic_name, m.brand_name, m.is_own_brand
ORDER BY week, t.topic_name, avg_visibility DESC;
```

### Výkon per engine (který engine je pro nás nejlepší?)

```sql
SELECT
  p.engine_id,
  m.is_own_brand,
  ROUND(AVG(IF(m.metric_type='VISIBILITY',    m.metric_value, NULL)), 3) AS avg_visibility,
  ROUND(AVG(IF(m.metric_type='POSITION_RANK', m.metric_value, NULL)), 1) AS avg_rank,
  ROUND(AVG(IF(m.metric_type='DETECTION_RATE',m.metric_value, NULL)), 3) AS avg_detection
FROM `libor-matejkacz.RankScaleDashboard.run_metrics`   m
JOIN `libor-matejkacz.RankScaleDashboard.prompt_runs`   r ON m.run_id    = r.run_id
JOIN `libor-matejkacz.RankScaleDashboard.prompts`       p ON r.prompt_id = p.prompt_id
GROUP BY p.engine_id, m.is_own_brand
ORDER BY p.engine_id, m.is_own_brand DESC;
```

### Top prompty kde zaostáváme za konkurencí

```sql
-- Prompty kde vlastní brand má nižší visibility než průměr konkurence
WITH brand_metrics AS (
  SELECT
    r.prompt_id,
    p.prompt_text,
    t.topic_name,
    p.engine_id,
    AVG(IF(m.is_own_brand AND m.metric_type='VISIBILITY', m.metric_value, NULL))  AS own_visibility,
    AVG(IF(NOT m.is_own_brand AND m.metric_type='VISIBILITY', m.metric_value, NULL)) AS comp_avg_visibility
  FROM `libor-matejkacz.RankScaleDashboard.run_metrics`   m
  JOIN `libor-matejkacz.RankScaleDashboard.prompt_runs`   r ON m.run_id    = r.run_id
  JOIN `libor-matejkacz.RankScaleDashboard.prompts`       p ON r.prompt_id = p.prompt_id
  JOIN `libor-matejkacz.RankScaleDashboard.topics`        t ON p.topic_id  = t.topic_id
  GROUP BY r.prompt_id, p.prompt_text, t.topic_name, p.engine_id
)
SELECT
  topic_name,
  prompt_text,
  engine_id,
  ROUND(own_visibility, 3)      AS own_visibility,
  ROUND(comp_avg_visibility, 3) AS competitors_avg,
  ROUND(comp_avg_visibility - own_visibility, 3) AS gap
FROM brand_metrics
WHERE own_visibility IS NOT NULL
ORDER BY gap DESC
LIMIT 20;
```

---

## 6. Co tento návrh neumí

| Limitation | Workaround |
|---|---|
| Timeseries s denní granularitou | ETL pouštět denně místo týdně (Rankscale běží weekly, takže hodnoty budou identické do dalšího snapshotu) |
| Keyword sentiment v reportech | `metric_details` JSON na `SENTIMENT` záznamu – nelze přímo agregovat v SQL, nutný rozparsování |
| Citace per URL | Přidat tabulku `citations` (viz analýza), nebo ignorovat |
| Competitors bez `brand_id` (neznámí) | `brand_id = NULL` v run_metrics; filtrovatelné, ale nelze joinovat s `brands` |
| Historická data před spuštěním ETL | První run s `timeFrame: 1y` doplní historii, pak inkrementálně `7d` |
| Topic "Hypotéky" je v topics API ale má 0 search termů | Nezobrazí se v reportech – reálně neobsahuje žádná data |
