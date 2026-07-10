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
| Brand vs competitors per topic timeline | Extract 2 → `L0_report_table` |

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

### Krok 2 — Seznam topiců + tagy (per brand)
```
GET /v1/metrics/topics?brandRef=brand_id
GET /v1/metrics/search-terms?brandId=brand_id&limit=5000
```
Dvě volání, obě se neukládají přímo — slouží jako příprava pro krok 3.

**Topics** vrátí seznam aktivních topiců s jejich `searchTermIds`. Topicy bez search termů se přeskočí.

**Search-terms** vrátí všechny prompty včetně jejich tagů. Script sestaví mapping `topic_id → [unikátní tagy]` agregací tagů přes všechny search termy daného topicu. Tento mapping se předá do kroku 3 a uloží jako `tags` sloupec.

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

**Jak se uloží do `L0_report_table`:**
```
owning_brand_id       | topic_name | snapshot_date | brand_name       | is_own_brand | visibility_score
E5GAVmqco65u7Smx3hso | Brand      | 2026-06-02    | Česká spořitelna | TRUE         | 59.6
E5GAVmqco65u7Smx3hso | Brand      | 2026-06-09    | Česká spořitelna | TRUE         | 59.2
E5GAVmqco65u7Smx3hso | Brand      | 2026-06-02    | Air Bank         | FALSE        | 60.6
E5GAVmqco65u7Smx3hso | Brand      | 2026-06-09    | Air Bank         | FALSE        | 60.8
```

**Uloží do:** `L0_report_table`
- 1 řádek per brand (vlastní + každý competitor) per topic per týden

---

## Schéma volání

```
brands (1×)
  └── topics + search-terms (2× per brand)
        └── report per topic (N× per brand)   → L0_report_table
```

Příklad: 3 brandy, každý má 5 aktivních topiců = **21 API volání celkem** (3 + 3×2 + 3×5)

---

## Výstupní tabulky

### L0_report_table

| Sloupec | Popis |
|---|---|
| `owning_brand_id` | Brand jehož monitoring volání provedlo |
| `topic_id` | ID topicu |
| `topic_name` | Název topicu (Brand, Hypotéky, Půjčky/Úvěry...) |
| `tags` | JSON string unikátních tagů topicu, např. `'["product-brand","top-funnel"]'` |
| `snapshot_date` | Timestamp týdne (z API parallel array) |
| `brand_name` | Vlastní brand nebo competitor |
| `is_own_brand` | TRUE = vlastní brand |
| `visibility_score` | 0–100 |
| `sentiment` | 0–100 |
| `avg_position` | Průměrná pozice v AI odpovědi |
| `detection_rate` | % snapshotů kde byl brand detekován |
| `top3` | % výskytů na pozici 1–3 |
| `mentions` | Počet zmínek |
| `citations` | Počet citovaných URL |

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
FROM `libor-matejkacz.RankScaleDashboard.L0_report_table`
WHERE DATE(snapshot_date) = (
    SELECT MAX(DATE(snapshot_date))
    FROM `libor-matejkacz.RankScaleDashboard.L0_report_table`
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
FROM `libor-matejkacz.RankScaleDashboard.L0_report_table`
WHERE owning_brand_id = 'ZDE_BRAND_ID'
  AND is_own_brand    = TRUE
ORDER BY topic_name, tyden;
```
