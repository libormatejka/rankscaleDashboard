# Database Schema — AI SEO Dashboard

## Přehled architektury

Normalizované hvězdicové schéma. Tabulky jsou uloženy v BigQuery, joiny a transformace se řeší v Snowflake / Databricks.

---

## Tabulky

### 1. `brands`

| Sloupec | Typ | Popis |
|---|---|---|
| `brand_id` | STRING | PK (UUID) |
| `brand_name` | STRING | Název brandu nebo konkurenta |
| `entity_type` | STRING | `OWN_BRAND` / `COMPETITOR` |
| `website` | STRING | Volitelně |
| `created_at` | TIMESTAMP | |

---

### 2. `prompts`

| Sloupec | Typ | Popis |
|---|---|---|
| `prompt_id` | STRING | PK (UUID) |
| `prompt_text` | STRING | Text promptu |
| `brand_id` | STRING | FK → `brands.brand_id` |
| `is_active` | BOOL | Zda se prompt aktivně spouští |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

---

### 3. `tags`

Číselník všech dostupných štítků.

| Sloupec | Typ | Popis |
|---|---|---|
| `tag_id` | STRING | PK (UUID) |
| `tag_type` | STRING | Kategorie: `PRODUCT`, `CLUSTER`, `SEGMENT`, ... |
| `tag_value` | STRING | Hodnota: `"RankScale Pro"`, `"Enterprise"`, ... |
| `created_at` | TIMESTAMP | |

Unikátní constraint: `(tag_type, tag_value)`.

---

### 4. `prompt_tags`

Vazební tabulka M:N mezi prompty a štítky.

| Sloupec | Typ | Popis |
|---|---|---|
| `prompt_id` | STRING | FK → `prompts.prompt_id` |
| `tag_id` | STRING | FK → `tags.tag_id` |

---

### 5. `prompt_runs`

Každý záznam = jedno spuštění promptu s odpovědí AI.

| Sloupec | Typ | Popis |
|---|---|---|
| `run_id` | STRING | PK (UUID) |
| `prompt_id` | STRING | FK → `prompts.prompt_id` |
| `executed_at` | TIMESTAMP | Kdy byla odpověď získána |
| `ai_model` | STRING | Např. `gpt-4o`, `claude-sonnet-4-6`, `gemini-2.0-flash` |
| `ai_provider` | STRING | `openai`, `anthropic`, `google` |
| `response_text` | STRING | Plný text odpovědi |
| `prompt_snapshot` | STRING | Snapshot textu promptu v čase spuštění |
| `input_tokens` | INT64 | |
| `output_tokens` | INT64 | |

---

### 6. `run_metrics`

Každý záznam = jedna metrika pro jedno spuštění. EAV model — nová metrika = nový `metric_type`, žádná migrace schématu.

| Sloupec | Typ | Popis |
|---|---|---|
| `metric_id` | STRING | PK (UUID) |
| `run_id` | STRING | FK → `prompt_runs.run_id` |
| `metric_type` | STRING | Viz typy níže |
| `metric_value` | FLOAT64 | Numerická hodnota |
| `metric_label` | STRING | Textový štítek (`POSITIVE`, `NEGATIVE`, ...) |
| `metric_details` | JSON | Volitelný detail, sub-scores |
| `computed_at` | TIMESTAMP | |

#### Typy metrik (`metric_type`):

| Hodnota | Popis | `metric_value` rozsah |
|---|---|---|
| `VISIBILITY` | Jak prominentně je brand zmíněn | 0.0 – 1.0 |
| `SENTIMENT` | Pozitivita vnímání brandu | -1.0 – 1.0 |
| `BRAND_MENTION` | Počet zmínek brandu v odpovědi | 0 – N |
| `POSITION_RANK` | Pořadí brandu v odpovědi | 1 – N |
| `RECOMMENDATION` | Zda AI brand doporučuje | 0.0 / 1.0 |

---

## ERD (textový)

```
brands
  └──< prompts          (brand_id)
         ├──< prompt_tags    (prompt_id)  >──── tags
         └──< prompt_runs    (prompt_id)
                └──< run_metrics  (run_id)
```

---

## Dataset v BigQuery

```
project/
  └── ai_seo/
        ├── brands
        ├── prompts
        ├── tags
        ├── prompt_tags
        ├── prompt_runs
        └── run_metrics
```
