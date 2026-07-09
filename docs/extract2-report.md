# Extract 2 — Report Extract

Script: `src/rankscale_report_extract.py`
GitHub Action: `.github/workflows/extract_report.yml` (spouští se 7:00 UTC)

Paralelní extract k hlavnímu Extract 1. Stahuje agregovaná brand-level data z `/v1/metrics/report` endpointu — bez detailu per prompt, ale s čistou weekly timeline a plným competitor přehledem per topic.

---

## Kdy použít Extract 2 vs Extract 1

| Potřeba | Extract |
|---|---|
| Metriky per prompt | Extract 1 → `L1_fact_snapshots` |
| Texty AI odpovědí | Extract 1 → `L1_fact_answer_texts` |
| Citované weby | Extract 1 → `L1_fact_citations` |
| Brand vs competitors per topic timeline | Extract 2 → `raw_report_topic_brand` |

---

## Průběh extrakce

### Vstup
- `BACKFILL_START=YYYY-MM-DD` → stáhne od tohoto data do dnes
- prázdné → posledních 90 dní

### Krok 1 — Zjisti brandy
```
GET /v1/metrics/brands
```
Vrátí seznam vlastních brandů. `brand_id` a `brand_name` použijeme pro další volání.
**Neukládá se** — brands má Extract 1.

**Ukázka response:**
```json
{
  "brands": [
    { "id": "E5GAVmqco65u7Smx3hso", "name": "Česká spořitelna (Test)", "url": "csas.cz" },
    { "id": "tkek4nJAg1lrRbyhjqlM", "name": "Zonky", "url": "zonky.cz" }
  ]
}
```

---

### Krok 2 — Seznam topiců (per brand)
```
GET /v1/metrics/topics?brandRef=brand_id
```
Vrátí konfiguraci topiců. Přeskočíme topicy bez přiřazených search termů (prázdné `searchTermIds`).
**Neukládá se** — slouží jen jako číselník topic_id pro krok 4.

**Ukázka response (zkráceno):**
```json
{
  "topics": [
    { "id": "ZFyMrgG0cuuEAvCdf1nr", "name": "Brand",         "searchTermIds": ["xS7F...", "o72k...", "..."] },
    { "id": "aVaq5pTG3Io4GR853gAf", "name": "Půjčky/Úvěry", "searchTermIds": ["0Ce9...", "lJqM...", "..."] },
    { "id": "A4tgfyAXO2ekw5L64DNY", "name": "Hypotéky",      "searchTermIds": [] },
    { "id": "truYnsoK6ygBo1Ekgmez", "name": "Investice",     "searchTermIds": ["hh5F...", "zzA7...", "..."] }
  ]
}
```
`Hypotéky` má prázdné `searchTermIds` → přeskočíme, report by vrátil prázdná data.

---

### Krok 3 — Report per topic (per brand × per topic)
```
POST /v1/metrics/report
  { brandId, isoStartDate, isoEndDate, aggregation: "weekly",
    filters: { topicId: "..." } }
```
Stejný endpoint jako krok 2, filtrovaný na konkrétní topic. Vrátí vlastní brand + competitors s metrikami pouze pro prompty daného topicu.

**Ukázka response (zkráceno, topic=Brand):**
```json
{
  "ownBrandMetrics": {
    "historicalData": {
      "daily": {
        "visibilityScore": [59.6, 59.2, 57.8, 58.2],
        "sentiment":       [68.9, 68.8, 68.5, 69.2],
        "timestamps": ["2026-06-02T00:00:00.000Z", "2026-06-09T00:00:00.000Z", ...]
      }
    }
  },
  "competitorTimeSeriesData": {
    "daily": {
      "timestamps": ["2026-06-02T00:00:00.000Z", "2026-06-09T00:00:00.000Z", ...],
      "competitors": [
        {
          "name": "Air Bank",
          "metrics": { "visibilityScore": [60.6, 60.8, ...], "sentiment": [67.8, 68.4, ...] }
        }
      ]
    }
  }
}
```

**Jak se uloží do `raw_report_topic_brand`:**
```
owning_brand_id       | topic_name | snapshot_date | brand_name       | is_own_brand | visibility_score
E5GAVmqco65u7Smx3hso | Brand      | 2026-06-02    | Česká spořitelna | TRUE         | 59.6
E5GAVmqco65u7Smx3hso | Brand      | 2026-06-09    | Česká spořitelna | TRUE         | 59.2
E5GAVmqco65u7Smx3hso | Brand      | 2026-06-02    | Air Bank         | FALSE        | 60.6
E5GAVmqco65u7Smx3hso | Brand      | 2026-06-09    | Air Bank         | FALSE        | 60.8
```

**Uloží do:** `raw_report_topic_brand`
- 1 řádek per brand (vlastní + každý competitor) per topic per týden

---

## Schéma volání

```
brands (1×)
  └── topics (1× per brand)
        └── report per topic (N× per brand)   → raw_report_topic_brand
```

Příklad: 3 brandy, každý má 5 aktivních topiců = **18 API volání celkem**

---

## Výstupní tabulky

### raw_report_topic_brand



| Sloupec | Popis |
|---|---|
| `topic_id` | ID topicu |
| `topic_name` | Název topicu (Brand, Hypotéky, Půjčky/Úvěry...) |

---

## Ukázkové dotazy

```sql
-- Visibility vlastní brand vs competitors per topic, poslední týden
SELECT
  topic_name,
  brand_name,
  is_own_brand,
  visibility_score,
  RANK() OVER (PARTITION BY topic_name ORDER BY visibility_score DESC) AS poradi
FROM `libor-matejkacz.RankScaleDashboard.raw_report_topic_brand`
WHERE DATE(snapshot_date) = (
    SELECT MAX(DATE(snapshot_date))
    FROM `libor-matejkacz.RankScaleDashboard.raw_report_topic_brand`
  )
  AND owning_brand_id = 'ZDE_BRAND_ID'
ORDER BY topic_name, poradi;
```

```sql
-- Timeline visibility per topic pro vlastní brand
SELECT
  DATE(snapshot_date) AS tyden,
  topic_name,
  visibility_score,
  sentiment,
  detection_rate
FROM `libor-matejkacz.RankScaleDashboard.raw_report_topic_brand`
WHERE owning_brand_id = 'ZDE_BRAND_ID'
  AND is_own_brand    = TRUE
ORDER BY topic_name, tyden;
```
