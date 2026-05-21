# AI SEO Dashboard — Databázová dokumentace

## Obsah

1. [Architektura a datový tok](#1-architektura-a-datový-tok)
2. [Dataset a pojmenování](#2-dataset-a-pojmenování)
3. [Tabulky](#3-tabulky)
   - [brands](#31-brands)
   - [prompts](#32-prompts)
   - [prompt_runs](#33-prompt_runs)
   - [run_metrics](#34-run_metrics)
4. [Referenční hodnoty](#4-referenční-hodnoty)
5. [ERD](#5-erd)
6. [Příklady dotazů](#6-příklady-dotazů)
7. [Soubory](#7-soubory)

---

## 1. Architektura a datový tok

```
[AI modely]
    │  odpovědi na prompty
    ▼
[BigQuery — L0]          raw, normalizovaná data
    │  ETL přes Keboola
    ▼
[Snowflake — L1]         denormalizovaný wide table, agregace
    │
    ▼
[Tableau]                dashboardy, vývojové grafy
```

**BigQuery L0** slouží jako věrné uložiště surových dat. Neřeší výkon dotazů ani denormalizaci — to je zodpovědností transformační vrstvy v Keboole.

**Snowflake L1** bude obsahovat:
- `l1_prompt_runs_detail` — každý run s metrikami a kategoriemi pro drill-down
- `l1_metrics_weekly` — agregát po týdnech pro trend grafy

---

## 2. Dataset a pojmenování

| Položka | Hodnota |
|---|---|
| GCP projekt | `libor-matejkacz` |
| BigQuery dataset | `RankScaleDashboard` |
| Plně kvalifikovaný název | `` `libor-matejkacz.RankScaleDashboard.<tabulka>` `` |

---

## 3. Tabulky

### 3.1 `brands`

Číselník sledovaných brandů. Rozlišuje vlastní brand od konkurentů.

```sql
CREATE TABLE `libor-matejkacz.RankScaleDashboard.brands` (
  brand_id    STRING    NOT NULL,
  brand_name  STRING    NOT NULL,
  entity_type STRING    NOT NULL,
  website     STRING,
  created_at  TIMESTAMP NOT NULL
)
```

| Sloupec | Typ | Povinný | Popis |
|---|---|---|---|
| `brand_id` | STRING | ✓ | Primární klíč (UUID) |
| `brand_name` | STRING | ✓ | Název brandu nebo konkurenta |
| `entity_type` | STRING | ✓ | `OWN_BRAND` nebo `COMPETITOR` |
| `website` | STRING | | Doménové jméno |
| `created_at` | TIMESTAMP | ✓ | Datum vytvoření záznamu |

**Aktuální data:**

| brand_id | brand_name | entity_type |
|---|---|---|
| brand-001 | RankScale | OWN_BRAND |
| brand-002 | Ahrefs | COMPETITOR |
| brand-003 | Semrush | COMPETITOR |
| brand-004 | Moz | COMPETITOR |

---

### 3.2 `prompts`

Šablony promptů zadávaných AI modelům. Každý prompt je přiřazen konkrétnímu brandu a kategoricky zařazen pomocí přímých sloupců.

```sql
CREATE TABLE `libor-matejkacz.RankScaleDashboard.prompts` (
  prompt_id   STRING    NOT NULL,
  prompt_text STRING    NOT NULL,
  brand_id    STRING    NOT NULL,
  product     STRING    NOT NULL,
  source      STRING    NOT NULL,
  segment     STRING,
  funnel      STRING    NOT NULL,
  type        STRING    NOT NULL,
  is_active   BOOL      NOT NULL,
  created_at  TIMESTAMP NOT NULL,
  updated_at  TIMESTAMP NOT NULL
)
```

| Sloupec | Typ | Povinný | Popis |
|---|---|---|---|
| `prompt_id` | STRING | ✓ | Primární klíč (UUID) |
| `prompt_text` | STRING | ✓ | Text promptu posílaného AI modelu |
| `brand_id` | STRING | ✓ | FK → `brands.brand_id` |
| `product` | STRING | ✓ | Produktová kategorie — viz [referenční hodnoty](#41-product) |
| `source` | STRING | ✓ | Zdroj/kanál promptu — viz [referenční hodnoty](#42-source) |
| `segment` | STRING | | Tržní segment — hodnoty budou upřesněny |
| `funnel` | STRING | ✓ | Fáze nákupního trychtýře — viz [referenční hodnoty](#43-funnel) |
| `type` | STRING | ✓ | Typ dotazu — viz [referenční hodnoty](#44-type) |
| `is_active` | BOOL | ✓ | `TRUE` = prompt se aktivně spouští |
| `created_at` | TIMESTAMP | ✓ | Datum vytvoření |
| `updated_at` | TIMESTAMP | ✓ | Datum poslední úpravy |

**Vztahy:** Jeden brand může mít více promptů. Stejný text promptu může existovat pro různé brandy (umožňuje přímé srovnání odpovědí AI na identický dotaz).

---

### 3.3 `prompt_runs`

Faktová tabulka. Každý záznam představuje jedno spuštění promptu — odeslání dotazu AI modelu a uložení jeho odpovědi.

```sql
CREATE TABLE `libor-matejkacz.RankScaleDashboard.prompt_runs` (
  run_id          STRING    NOT NULL,
  prompt_id       STRING    NOT NULL,
  executed_at     TIMESTAMP NOT NULL,
  ai_model        STRING    NOT NULL,
  ai_provider     STRING    NOT NULL,
  response_text   STRING,
  prompt_snapshot STRING,
  input_tokens    INT64,
  output_tokens   INT64
)
PARTITION BY DATE(executed_at)
CLUSTER BY ai_provider, ai_model
```

| Sloupec | Typ | Povinný | Popis |
|---|---|---|---|
| `run_id` | STRING | ✓ | Primární klíč (UUID) |
| `prompt_id` | STRING | ✓ | FK → `prompts.prompt_id` |
| `executed_at` | TIMESTAMP | ✓ | Čas získání odpovědi od AI modelu |
| `ai_model` | STRING | ✓ | Identifikátor modelu, např. `gpt-4o`, `claude-sonnet-4-6`, `gemini-2.0-flash` |
| `ai_provider` | STRING | ✓ | Poskytovatel: `openai`, `anthropic`, `google` |
| `response_text` | STRING | | Plný text odpovědi AI |
| `prompt_snapshot` | STRING | | Snapshot textu promptu v čase spuštění (pro případ změny originálu) |
| `input_tokens` | INT64 | | Počet vstupních tokenů (pro sledování nákladů) |
| `output_tokens` | INT64 | | Počet výstupních tokenů |

**Partitionování:** `DATE(executed_at)` — dotazy filtrované po datu neprochází celou tabulkou.

**Clusterování:** `ai_provider, ai_model` — efektivní filtrování při analýze konkrétního modelu nebo providera.

---

### 3.4 `run_metrics`

Faktová tabulka metrik. Každý záznam je jedna vypočítaná metrika pro jedno spuštění promptu. Struktura EAV (Entity–Attribute–Value) umožňuje přidávat nové typy metrik bez změny schématu.

```sql
CREATE TABLE `libor-matejkacz.RankScaleDashboard.run_metrics` (
  metric_id      STRING    NOT NULL,
  run_id         STRING    NOT NULL,
  metric_type    STRING    NOT NULL,
  metric_value   FLOAT64   NOT NULL,
  metric_label   STRING,
  metric_details JSON,
  computed_at    TIMESTAMP NOT NULL
)
PARTITION BY DATE(computed_at)
CLUSTER BY metric_type
```

| Sloupec | Typ | Povinný | Popis |
|---|---|---|---|
| `metric_id` | STRING | ✓ | Primární klíč (UUID) |
| `run_id` | STRING | ✓ | FK → `prompt_runs.run_id` |
| `metric_type` | STRING | ✓ | Typ metriky — viz [referenční hodnoty](#45-metric_type) |
| `metric_value` | FLOAT64 | ✓ | Numerická hodnota metriky |
| `metric_label` | STRING | | Textový štítek (používá se u SENTIMENT: `POSITIVE`, `NEUTRAL`, `NEGATIVE`) |
| `metric_details` | JSON | | Doplňující detail, sub-scores, zdůvodnění |
| `computed_at` | TIMESTAMP | ✓ | Čas výpočtu metriky |

**Partitionování:** `DATE(computed_at)`

**Clusterování:** `metric_type` — efektivní filtrování při dotazech na konkrétní metriku (např. pouze VISIBILITY).

---

## 4. Referenční hodnoty

### 4.1 `product`

Produktová linie, které se prompt týká.

| Hodnota | Popis |
|---|---|
| `brand` | Obecné povědomí o brandu a jeho vnímání |
| `loan` | Spotřebitelské úvěry a půjčky |
| `hypo` | Hypoteční produkty |

### 4.2 `source`

Kanál nebo způsob, jakým byl prompt získán/definován.

| Hodnota | Popis |
|---|---|
| `SEO` | Dotazy odvozené z organického vyhledávání |
| `Survey` | Dotazy z průzkumů zákazníků |
| `Community` | Dotazy z komunitních diskusí a fór |
| `Custom` | Ručně definované / ad-hoc prompty |

### 4.3 `funnel`

Fáze nákupního trychtýře (See–Think–Do–Care framework).

| Hodnota | Popis | Příklad záměru |
|---|---|---|
| `See` | Povědomí — uživatel ještě aktivně nehledá | „Co je hypotéka?" |
| `Think` | Zvažování — uživatel porovnává možnosti | „Jaká je nejlepší hypotéka pro mladé rodiny?" |
| `Do` | Akce — uživatel je připraven jednat | „Jak sjednat hypotéku online?" |
| `Care` | Péče — stávající zákazník | „Jak refinancovat stávající hypotéku?" |

### 4.4 `type`

Typ dotazu z hlediska záměru uživatele.

| Hodnota | Popis |
|---|---|
| `inform` | Informační dotaz — uživatel hledá znalosti |
| `transaction` | Transakční dotaz — uživatel hledá akci nebo produkt |

### 4.5 `metric_type`

| Hodnota | Rozsah `metric_value` | Popis |
|---|---|---|
| `VISIBILITY` | 0.0 – 1.0 | Jak prominentně je brand zmíněn v odpovědi |
| `SENTIMENT` | -1.0 – 1.0 | Pozitivita / negativita vnímání brandu |
| `BRAND_MENTION` | 0 – N (celé číslo) | Počet zmínek brandu v textu odpovědi |
| `POSITION_RANK` | 1 – N (celé číslo) | Pořadí první zmínky brandu (1 = nejdříve zmíněn) |
| `RECOMMENDATION` | 0.0 nebo 1.0 | Zda AI model brand aktivně doporučuje |

---

## 5. ERD

```
┌─────────────┐
│   brands    │
│─────────────│
│ brand_id PK │◄──────────────────┐
│ brand_name  │                   │
│ entity_type │                   │
│ website     │                   │
│ created_at  │                   │
└─────────────┘                   │
                                  │
┌──────────────────┐              │
│     prompts      │              │
│──────────────────│              │
│ prompt_id    PK  │◄──────┐      │
│ prompt_text      │       │      │
│ brand_id     FK  │───────┼──────┘
│ product          │       │
│ source           │       │
│ segment          │       │
│ funnel           │       │
│ type             │       │
│ is_active        │       │
│ created_at       │       │
│ updated_at       │       │
└──────────────────┘       │
                           │
┌──────────────────────┐   │
│     prompt_runs      │   │
│──────────────────────│   │
│ run_id       PK      │◄──┼──┐
│ prompt_id    FK      │───┘  │
│ executed_at          │      │
│ ai_model             │      │
│ ai_provider          │      │
│ response_text        │      │
│ prompt_snapshot      │      │
│ input_tokens         │      │
│ output_tokens        │      │
└──────────────────────┘      │
                              │
┌──────────────────────┐      │
│     run_metrics      │      │
│──────────────────────│      │
│ metric_id    PK      │      │
│ run_id       FK      │──────┘
│ metric_type          │
│ metric_value         │
│ metric_label         │
│ metric_details       │
│ computed_at          │
└──────────────────────┘
```

---

## 6. Příklady dotazů

### Průměrná Visibility podle brandu

```sql
SELECT
  b.brand_name,
  b.entity_type,
  ROUND(AVG(m.metric_value), 3) AS avg_visibility,
  COUNT(*)                       AS run_count
FROM `libor-matejkacz.RankScaleDashboard.run_metrics`   m
JOIN `libor-matejkacz.RankScaleDashboard.prompt_runs`   r ON m.run_id    = r.run_id
JOIN `libor-matejkacz.RankScaleDashboard.prompts`       p ON r.prompt_id = p.prompt_id
JOIN `libor-matejkacz.RankScaleDashboard.brands`        b ON p.brand_id  = b.brand_id
WHERE m.metric_type = 'VISIBILITY'
GROUP BY b.brand_name, b.entity_type
ORDER BY avg_visibility DESC;
```

### Vývoj Visibility v čase — vlastní brand vs. konkurence

```sql
SELECT
  DATE_TRUNC(r.executed_at, WEEK) AS week,
  b.brand_name,
  b.entity_type,
  ROUND(AVG(m.metric_value), 3)   AS avg_visibility
FROM `libor-matejkacz.RankScaleDashboard.run_metrics`   m
JOIN `libor-matejkacz.RankScaleDashboard.prompt_runs`   r ON m.run_id    = r.run_id
JOIN `libor-matejkacz.RankScaleDashboard.prompts`       p ON r.prompt_id = p.prompt_id
JOIN `libor-matejkacz.RankScaleDashboard.brands`        b ON p.brand_id  = b.brand_id
WHERE m.metric_type = 'VISIBILITY'
GROUP BY week, b.brand_name, b.entity_type
ORDER BY week, b.entity_type DESC;
```

### Metriky breaknuté podle produktu (vlastní brand)

```sql
SELECT
  p.product,
  p.funnel,
  ROUND(AVG(IF(m.metric_type = 'VISIBILITY', m.metric_value, NULL)), 3) AS avg_visibility,
  ROUND(AVG(IF(m.metric_type = 'SENTIMENT',  m.metric_value, NULL)), 3) AS avg_sentiment,
  COUNT(DISTINCT r.run_id)                                               AS run_count
FROM `libor-matejkacz.RankScaleDashboard.run_metrics`   m
JOIN `libor-matejkacz.RankScaleDashboard.prompt_runs`   r ON m.run_id    = r.run_id
JOIN `libor-matejkacz.RankScaleDashboard.prompts`       p ON r.prompt_id = p.prompt_id
JOIN `libor-matejkacz.RankScaleDashboard.brands`        b ON p.brand_id  = b.brand_id
WHERE b.entity_type = 'OWN_BRAND'
GROUP BY p.product, p.funnel
ORDER BY p.product, p.funnel;
```

### Srovnání modelů — průměrný Sentiment pro vlastní brand

```sql
SELECT
  r.ai_provider,
  r.ai_model,
  ROUND(AVG(m.metric_value), 3) AS avg_sentiment,
  COUNT(*)                       AS run_count
FROM `libor-matejkacz.RankScaleDashboard.run_metrics`   m
JOIN `libor-matejkacz.RankScaleDashboard.prompt_runs`   r ON m.run_id    = r.run_id
JOIN `libor-matejkacz.RankScaleDashboard.prompts`       p ON r.prompt_id = p.prompt_id
JOIN `libor-matejkacz.RankScaleDashboard.brands`        b ON p.brand_id  = b.brand_id
WHERE m.metric_type = 'SENTIMENT'
  AND b.entity_type = 'OWN_BRAND'
GROUP BY r.ai_provider, r.ai_model
ORDER BY avg_sentiment DESC;
```

### Recommendation rate podle source kanálu

```sql
SELECT
  p.source,
  b.entity_type,
  ROUND(AVG(m.metric_value), 3)  AS recommendation_rate,
  COUNT(*)                        AS run_count
FROM `libor-matejkacz.RankScaleDashboard.run_metrics`   m
JOIN `libor-matejkacz.RankScaleDashboard.prompt_runs`   r ON m.run_id    = r.run_id
JOIN `libor-matejkacz.RankScaleDashboard.prompts`       p ON r.prompt_id = p.prompt_id
JOIN `libor-matejkacz.RankScaleDashboard.brands`        b ON p.brand_id  = b.brand_id
WHERE m.metric_type = 'RECOMMENDATION'
GROUP BY p.source, b.entity_type
ORDER BY p.source, recommendation_rate DESC;
```

---

## 7. Soubory

| Soubor | Popis |
|---|---|
| [sql/schema.sql](../sql/schema.sql) | DDL — CREATE TABLE pro všechny tabulky |
| [sql/seed_data.sql](../sql/seed_data.sql) | Testovací data (4 brandy, 11 promptů, 19 runů, 95 metrik) |
| [.claude/database.md](../.claude/database.md) | Pracovní poznámky k návrhu schématu |
