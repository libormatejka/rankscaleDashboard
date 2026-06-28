# ETL – Celý průběh pipeline krok za krokem

## Přehled

```
GitHub Actions (cron 6:00 UTC)
        │
        ▼
src/rankscale_etl.py
        │
        ├── KROK 1: brands         → GET  /v1/metrics/brands
        ├── KROK 2: search_terms   → GET  /v1/metrics/search-terms (per brand)
        │       │
        │       └── Freshness check ──► pokud nic nového → STOP
        │
        ├── KROK 3: brand_snapshots → POST /v1/metrics/search-terms-report (per brand)
        ├── KROK 4: answer_texts    → POST /v1/metrics/search-terms-report + answerTexts (per brand)
        └── KROK 5: citations       → POST /v1/metrics/citations (per brand)
```

---

## KROK 1 — Brands

**Endpoint:** `GET /v1/metrics/brands`

**Co vrátí:** Seznam všech brandů v Rankscale workspace — vlastní brand i sledovaní konkurenti.

**Co ETL udělá:**
1. Zavolá endpoint, dostane JSON se seznamem brandů
2. Každému řádku přidá `is_active: True` a `loaded_at: now()`
3. Uloží do BigQuery tabulky `brands` přes **UPSERT**:
   - Existující brand → UPDATE (aktualizují se hodnoty)
   - Nový brand → INSERT
   - Brand který v API chybí (smazán v Rankscale) → `is_active = FALSE` (řádek zůstane)
4. Vrátí seznam všech `brand_id` — ty se použijí v krocích 2–5

**BQ tabulka:** `brands`
**Staging tabulka:** `brands_staging` (dočasná, lze ignorovat)

---

## KROK 2 — Search terms

**Endpoint:** `GET /v1/metrics/search-terms?brandId={brand_id}`

**Co vrátí:** Všechny sledované search termy (prompt × engine kombinace) pro daný brand.

**Co ETL udělá:**
1. Projde všechny `brand_id` z kroku 1
2. Pro každý brand zavolá endpoint
3. Všechny řádky ze všech brandů sloučí do jednoho listu
4. Deduplikuje podle `search_term_id` (pro případ duplicit z API)
5. Uloží do `search_terms` přes **UPSERT** (stejná logika jako brands)
6. Zapamatuje si `MAX(lastExecutionTime)` ze všech stažených termů — timestamp posledního Rankscale snapshotu

**BQ tabulka:** `search_terms`
**Staging tabulka:** `search_terms_staging` (dočasná, lze ignorovat)

---

## Freshness check

**Po kroku 2, před krokem 3.**

ETL porovná dvě hodnoty:
- `bq_max` = `MAX(last_snapshot_at)` dotazem do BQ tabulky `brand_snapshots`
- `api_max` = `MAX(lastExecutionTime)` z právě stažených search termů

**Rozhodnutí:**
- `api_max <= bq_max` → BQ je stejně aktuální nebo novější než Rankscale → **kroky 3–5 se přeskočí**
- `api_max > bq_max` → Rankscale má novější data → **pokračuje se kroky 3–5**

**Proč:** Rankscale dělá snapshoty jednou týdně. ETL běží denně. 6 ze 7 dní tedy není co nového stahovat — freshness check ušetří 3 zbytečné API cally a čas.

---

## KROK 3 — Brand snapshots

**Endpoint:** `POST /v1/metrics/search-terms-report`

**Tělo requestu:**
```json
{
  "brandId": "...",
  "timeFrame": "7d",
  "includeCompetitors": true
}
```

**Co vrátí:** Metriky per search term za posledních 7 dní — jak pro vlastní brand, tak pro konkurenty detekované v AI odpovědích.

**Klíčové metriky:**
| Pole | Popis |
|------|-------|
| `visibility_score` | 0–100; jak prominentně AI brand zmiňuje |
| `avg_sentiment` | 0–100; 50 = neutrální, >50 pozitivní |
| `avg_rank` | průměrná pozice v AI odpovědi (1 = nejlepší) |
| `detection_rate` | % snapshotů kde byl brand detekován |
| `top3_rate` | % výskytů na pozici 1–3 |

**Co ETL udělá:**
1. Projde všechny `brand_id`
2. Pro každý brand zavolá endpoint
3. Uloží do `brand_snapshots` přes **partition overwrite**:
   - Data se rozdělí podle `snapshot_date`
   - Každý unikátní datum = jedna partition
   - Přepíší se pouze partitions které jsou v aktuálních datech
   - Starší historická data zůstanou nedotčena

**BQ tabulka:** `brand_snapshots`

---

## KROK 4 — Answer texts

**Endpoint:** `POST /v1/metrics/search-terms-report` (stejný jako krok 3)

**Tělo requestu:**
```json
{
  "brandId": "...",
  "timeFrame": "7d",
  "includeAnswerTexts": true
}
```

**Co vrátí:** Raw texty AI odpovědí pro každý search term a každou exekuci.

**Co ETL udělá:**
1. Projde všechny `brand_id`
2. Pro každý brand zavolá endpoint s `includeAnswerTexts: true`
3. Před zápisem načte z BQ všechna existující `execution_id`
4. Z nových dat odfiltruje ty `execution_id` které už v BQ jsou
5. Zapíše jen skutečně nové záznamy (**APPEND + dedup**)

**Proč ne partition overwrite:** Texty odpovědí jsou historické záznamy — jednou vygenerovaná odpověď se nikdy nemění. Přepsání partition by způsobilo ztrátu starších textů.

**BQ tabulka:** `answer_texts`

---

## KROK 5 — Citations

**Endpoint:** `POST /v1/metrics/citations`

**Tělo requestu:**
```json
{
  "brandId": "...",
  "timeFrame": "7d"
}
```

**Co vrátí:** Citované domény a URL per query a engine — tedy které weby AI engine zmiňoval jako zdroje v odpovědích na sledované prompty.

**Co ETL udělá:**
1. Projde všechny `brand_id`
2. Pro každý brand zavolá endpoint
3. Z odpovědi vytáhne `domainSummary.topDomainsByQuery`
4. Uloží do `citations` přes **partition overwrite** (stejná logika jako krok 3)

**BQ tabulka:** `citations`

---

## Jak funguje UPSERT (kroky 1 a 2)

```
Python list (rows)
      │
      ▼ deduplikace podle key_col (v Pythonu)
      │
      ▼ zápis do staging tabulky (WRITE_TRUNCATE)
      │  brands_staging / search_terms_staging
      │
      ▼ BigQuery MERGE
         ┌─────────────────────────────────────────────┐
         │ MERGE brands AS T                           │
         │ USING brands_staging AS S                   │
         │ ON T.brand_id = S.brand_id                  │
         │                                             │
         │ WHEN MATCHED                                │
         │   → UPDATE (aktualizuj všechny hodnoty)     │
         │                                             │
         │ WHEN NOT MATCHED BY TARGET                  │
         │   → INSERT (nový záznam)                    │
         │                                             │
         │ WHEN NOT MATCHED BY SOURCE                  │
         │   → UPDATE SET is_active = FALSE            │
         │     (v API chybí = smazán v Rankscale)      │
         └─────────────────────────────────────────────┘
```

Staging tabulky (`brands_staging`, `search_terms_staging`) zůstanou v datasetu i po dokončení. Při příštím runu se přepíšou. Jejich obsah je vždy identický s právě nahranými daty — lze je ignorovat.

---

## Jak funguje Partition overwrite (kroky 3 a 5)

```
Python list (rows)
      │
      ▼ rozdělení podle snapshot_date
      │
      ▼ pro každý unikátní datum:
         zápis do BQ s WRITE_TRUNCATE pro danou partition
         (ostatní partitions jsou nedotčeny)
```

Příklad: ETL stahuje `TIME_FRAME = 7d`, data obsahují datumy `2026-06-22` až `2026-06-28`. Přepíše se pouze těchto 7 partitions. Data z `2026-06-01` zůstanou.

---

## Výsledek úspěšného runu

| Tabulka | Co se změnilo |
|---------|--------------|
| `brands` | Aktuální stav všech brandů; smazané mají `is_active = FALSE` |
| `search_terms` | Aktuální stav všech promptů; smazané mají `is_active = FALSE` |
| `brand_snapshots` | Metriky za posledních 7 dní (partition overwrite) |
| `answer_texts` | Nové AI odpovědi které dosud nebyly v BQ |
| `citations` | Citace za posledních 7 dní (partition overwrite) |

---

## Kde co najít

| Soubor | Obsah |
|--------|-------|
| `src/rankscale_etl.py` | Celý ETL kód |
| `sql/schema_rankscale.sql` | DDL pro vytvoření tabulek |
| `docs/bigquery-data-model.md` | Popis sloupců a SQL příklady |
| `docs/etl-loading-strategy.md` | Proč jaká strategie zápisu |
| `docs/rankscale-endpoints.md` | Popis API endpointů |
