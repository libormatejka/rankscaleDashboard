# Pipeline — kompletní průvodce

Celý tok dat od Rankscale API až do BI nástroje.

---

## Architektura na jedné stránce

```
Rankscale API
     │
     │  každý den 6:30 UTC  (GitHub Actions: extract.yml)
     ▼
┌──────────────────────────────────────────────────────┐
│  rankscale_extract.py                                │
│  Stáhni data z API a ulož 1:1 do BigQuery            │
└──────────────────────────────────────────────────────┘
     │
     ▼
raw_ tabulky (BigQuery)
  raw_brands, raw_search_terms, raw_brand_snapshots,
  raw_answer_texts, raw_citations
  → každý den se přidají nové řádky (APPEND), nic se nesmaže
     │
     │  transform_l1.sql  (spustit ručně nebo Keboola)
     ▼
L1_ tabulky (BigQuery)
  L1_dim_brands, L1_dim_search_terms, L1_fact_snapshots,
  L1_fact_citations, L1_fact_answer_texts
  → deduplikovaná data, business logika (is_active, ai_share_of_voice)
     │
     │  transform_l2.sql  (spustit ručně nebo Keboola)
     ▼
L2_ tabulky (BigQuery)
  L2_snapshots, L2_search_term_tags,
  L2_citations, L2_answer_texts
  → vše předjoinované, připraveno pro BI bez dalších transformací
     │
     ▼
Tableau / Looker Studio / Power BI
```

---

## Co je TIME_FRAME a jak funguje

`TIME_FRAME` říká Rankscale API, za jaké **historické období** má vrátit data.

| Hodnota | Popis |
|---|---|
| `7d` | Posledních 7 dní — **výchozí hodnota** |
| `30d` | Posledních 30 dní |
| `3m` | Poslední 3 měsíce |
| `1y` | Poslední rok — použij pro první backfill |

**Důležité:** `TIME_FRAME` neovlivňuje, co se stáhne do `raw_brands` a `raw_search_terms` — ty vždy vrátí aktuální seznam bez ohledu na časové okno. Ovlivňuje pouze metrická data: `raw_brand_snapshots`, `raw_answer_texts` a `raw_citations`.

**Příklad s `TIME_FRAME=7d`:**
- `raw_brand_snapshots` dostane metriky za posledních 7 dní (visibility, sentiment, rank...)
- Pokud jsou prompty nastaveny na weekly interval, dostaneš typicky 1 snapshot per prompt
- Pokud jsou na daily, dostaneš až 7 snapshotů per prompt

**Proč tedy stahujeme 7d každý den?**
Rankscale počítá metriky průběžně a může je zpětně upravit. Stahováním posledních 7 dní každý den zajistíme, že máme vždy aktuální data i pro záznamy z minulého týdne.

---

## KROK 1 — Extract (rankscale_extract.py)

### Co se stahuje a v jakém pořadí

```
1. brands         →  kdo jsme (brand_id)
2. search_terms   →  jaké prompty sledujeme (per brand)
3. brand_snapshots  →  metriky brandů per prompt
4. answer_texts   →  plné texty AI odpovědí
5. citations      →  které weby AI citoval
```

Kroky 3–5 se **opakují pro každý brand**. Pokud jeden brand selže (API chyba), ostatní pokračují.

---

### raw_brands — kdo jsou naše brandy

**Endpoint:** `GET /v1/metrics/brands`

Vrátí seznam všech brandů v Rankscale workspace. U nás jsou to 2 brandy:
- `E5GAVmqco65u7Smx3hso` — Česká spořitelna
- `tkek4nJAg1lrRbyhjqlM` — druhý brand

| Sloupec v raw_brands | Odkud z API | Co znamená |
|---|---|---|
| `brand_id` | `brands[].id` | Unikátní ID brandu v Rankscale |
| `name` | `brands[].name` | Název brandu |
| `domain` | `brands[].url` | URL brandu |
| `is_own_brand` | vždy `TRUE` | Brands endpoint vrací jen naše vlastní brandy, ne competitors |
| `etl_loaded_at` | přidává script | Kdy jsme data stáhli |

> **Competitors** — brandy jako Air Bank, ČSOB apod. — nejsou v `/brands`. Objevují se až v brand_snapshots jako detekovaná konkurence v AI odpovědích.

---

### raw_search_terms — jaké prompty sledujeme

**Endpoint:** `GET /v1/metrics/search-terms?brandId=...&limit=5000`

Vrátí seznam všech sledovaných promptů pro daný brand. Jeden záznam = **1 prompt × 1 engine**. Stejný text promptu se opakuje tolikrát, na kolika enginech běží.

| Sloupec v raw_search_terms | Odkud z API | Co znamená |
|---|---|---|
| `search_term_id` | `searchTerms[].id` | Unikátní ID záznamu (prompt × engine) |
| `brand_id` | z parametru volání | Čí brand tento prompt patří |
| `query` | `searchTerms[].term` | Text promptu posílaného do AI |
| `engine` | `searchTerms[].aiSearchEngines[0]` | AI engine (`chatgpt_gui`, `google_ai_mode_gui`...) |
| `topic_id` | `searchTerms[].searchTermTopicRef.id` | ID produktové vertikály |
| `topic_name` | `searchTerms[].searchTermTopicRef.name` | Název vertikály (Půjčky, Hypotéky...) |
| `tags` | `searchTerms[].tags` | Pole tagů jako JSON string `'["product-brand"]'` |
| `region` | `searchTerms[].region` | Geografický region (`cz`, `sk`...) |
| `interval` | `searchTerms[].interval` | Frekvence spouštění (`weekly`, `daily`) |
| `status` | `searchTerms[].status` | `"active"` nebo `"inactive"` |
| `last_execution_time` | `searchTerms[].lastExecutionTime` | Kdy byl prompt naposledy spuštěn |
| `next_execution_time` | `searchTerms[].nextScheduledExecutionTime` | Kdy bude spuštěn příště |
| `executions_amount` | `searchTerms[].executionsAmount` | Celkový počet spuštění |
| `etl_loaded_at` | přidává script | Kdy jsme data stáhli |

**Limit 5000:** API má výchozí limit stránek. Posíláme `limit=5000` abychom stáhli vždy všechny prompty najednou (jeden brand má přes 1500 promptů).

---

### raw_brand_snapshots — metriky brandů per prompt

**Endpoint:** `POST /v1/metrics/search-terms-report`

Toto je **hlavní datová tabulka**. Vrátí metriky pro každý prompt — jak pro vlastní brand, tak pro všechny competitors detekované v AI odpovědích.

Jeden záznam = **1 brand (nebo competitor) × 1 prompt × 1 ETL run**.

| Sloupec v raw_brand_snapshots | Odkud z API | Co znamená |
|---|---|---|
| `brand_id` | z parametru volání | Čí brand monitoring tento záznam patří |
| `search_term_id` | `searchTerms[].searchTermId` | Který prompt |
| `engine` | `searchTerms[].aiSearchEngines[0]` | Který AI engine |
| `topic_id` | `searchTerms[].topic.id` | Topic platný v době snapshotu |
| `topic_name` | `searchTerms[].topic.name` | Název topicu v době snapshotu |
| `last_snapshot_at` | `searchTerms[].lastSnapshotAt` | Kdy Rankscale udělal snapshot (→ **snapshot_date** v L1/L2) |
| `brand_name` | `ownBrand.name` nebo `competitors[].name` | Název brandu v AI odpovědi |
| `is_own_brand` | `isOwnBrand` | TRUE = vlastní brand, FALSE = competitor |
| `visibility_score` | `visibilityScore` | 0–100; jak prominentně AI brand zmiňuje |
| `avg_sentiment` | `avgSentiment` | 0–100; 50 = neutrální, >50 = pozitivní |
| `avg_rank` | `avgRank` | Průměrná pozice v AI odpovědi (1 = nejlepší) |
| `latest_rank` | `latestRank` | Pozice v posledním konkrétním snapshotu |
| `detection_rate` | `detectionRate` | % snapshotů kde byl brand detekován (0–100) |
| `top3_rate` | `top3` | % výskytů na pozici 1–3 (0–100) |
| `citation_count` | `citationCount` | Počet citovaných URL |
| `appearances` | `appearances` | Počet snapshotů kde se brand objevil |
| `etl_loaded_at` | přidává script | Kdy jsme data stáhli |

**Vlastní brand vs. competitors:** API vrátí vlastní brand v poli `ownBrand{}` a competitors v poli `competitors[]`. Script je oba uloží jako samostatné řádky do stejné tabulky — odlišuje je `is_own_brand`.

---

### raw_answer_texts — texty AI odpovědí

**Endpoint:** `POST /v1/metrics/search-terms-report` (s `includeAnswerTexts: true`)

Jeden záznam = **1 konkrétní AI odpověď** (`execution_id`). Každý týden přibývají nové odpovědi.

| Sloupec | Co znamená |
|---|---|
| `execution_id` | Unikátní ID konkrétní exekuce — nikdy se neopakuje |
| `search_term_id` | Pro který prompt tato odpověď vznikla |
| `executed_at` | Kdy AI engine odpověděl — **toto použij pro timeline textů** |
| `engine` | Který AI engine odpovídal |
| `answer_text` | Plný text AI odpovědi (markdown, může obsahovat tabulky) |

---

### raw_citations — které weby AI citoval

**Endpoint:** `POST /v1/metrics/citations`

Jeden záznam = **1 URL × 1 engine × 1 search term**. Říká, které weby AI zmiňoval jako zdroje v odpovědích na naše prompty.

| Sloupec | Co znamená |
|---|---|
| `domain` | Doména citovaného webu, např. `banky.cz` |
| `url` | Konkrétní citovaná URL |
| `occurrences` | Kolikrát byla tato URL citována v daném období |
| `engine` | Který engine citaci použil |
| `search_term_id` | V kontextu kterého promptu |

---

## KROK 2 — L1 transformace (transform_l1.sql)

Z raw dat vznikají čisté, deduplikované tabulky. Každý den **full refresh** — celá tabulka se přepočítá znovu z raw dat.

**Proč je L1 potřeba:**
raw tabulky mají každý den nové řádky (APPEND). Po 30 dnech má každý prompt 30 řádků v `raw_search_terms` — jeden per ETL run. L1 to deduplikuje na 1 řádek per entitu a přidá výpočty.

### Jak funguje deduplikace

```sql
ROW_NUMBER() OVER (PARTITION BY search_term_id ORDER BY etl_loaded_at DESC) = 1
-- vezmi vždy jen nejnovější řádek per search_term_id
```

### Co se v L1 počítá

**`is_active` v L1_dim_brands:**
- `TRUE` = brand se objevil v posledním ETL runu
- `FALSE` = brand byl smazán v Rankscale (chybí v posledním stažení)

**`is_active` v L1_dim_search_terms:**
- Odvozeno přímo z `status` pole v API: `status = 'active'`

**`snapshot_week` a `snapshot_date` v L1_fact_snapshots:**
- Odvozeno z `last_snapshot_at` — kdy Rankscale snapshot provedl
- `snapshot_week` = ISO týden, např. `"2026-26"` — **hlavní časová dimenze pro report**

**`ai_share_of_voice` v L1_fact_snapshots:**
```sql
visibility_score vlastního brandu
─────────────────────────────────────────────────────
SUM(visibility_score) všech brandů ve stejném promptu a týdnu
```

---

## KROK 3 — L2 transformace (transform_l2.sql)

Z L1 vznikají plně denormalizované tabulky — vše předjoinované, BI nástroj jen zobrazuje.

**Proč je L2 potřeba:**
L1 je normalizovaná (dim/fact). Pro BI potřebuješ plochý datový model kde jsou všechny atributy na jednom místě — bez nutnosti joinovat topic_name, query, engine atd. v každém pohledu.

### Hlavní rozdíly L1 → L2

| Co se přidá do L2_snapshots (oproti L1_fact_snapshots) |
|---|
| `query` — text promptu (z L1_dim_search_terms) |
| `topic_name` — název vertikály |
| `tags` — JSON string tagů |
| `last_execution_time` — kdy byl prompt spuštěn |
| `owning_brand_id` — čí brand monitoring tento prompt patří (vždy vyplněno) |

### Tagy a L2_search_term_tags

Tagy jsou uloženy jako JSON string (`'["product-brand","top-funnel"]'`). BI nástroje s tím neumí přímo filtrovat.
`L2_search_term_tags` je bridge tabulka kde má každý tag vlastní řádek:

```
search_term_id | tag
─────────────────────────────
abc123         | product-brand
abc123         | top-funnel
xyz789         | product-brand
```

Pro filtr podle tagu stačí 1 join: `L2_snapshots JOIN L2_search_term_tags ON search_term_id WHERE tag = '...'`

---

## Datumy — který použít a proč

| Sloupec | Kde | Co říká | Použij pro |
|---|---|---|---|
| `snapshot_week` / `snapshot_date` | L1_fact_snapshots, L2_snapshots | Kdy Rankscale spočítal souhrnné metriky | **Timeline metrik — hlavní datum reportu** |
| `last_execution_time` | L1_dim_search_terms, L2_snapshots | Kdy byl prompt naposledy spuštěn | Zobrazení aktivity promptu |
| `executed_at` | L1_fact_answer_texts, L2_answer_texts | Kdy vznikla konkrétní AI odpověď | Řazení textů odpovědí |
| `etl_loaded_at` | raw_ tabulky | Kdy jsme stáhli data my | **Nepoužívej v reportu** — technický timestamp |

---

## Přehled všech tabulek a souborů

### Tabulky

```
raw_brands              ─┐
raw_search_terms         ├─  L0 — surová data, APPEND každý den
raw_brand_snapshots      │
raw_answer_texts         │
raw_citations           ─┘

L1_dim_brands           ─┐
L1_dim_search_terms      ├─  L1 — deduplikovaná data, full refresh
L1_fact_snapshots        │
L1_fact_citations        │
L1_fact_answer_texts    ─┘

L2_snapshots            ─┐
L2_search_term_tags      ├─  L2 — denormalizovaná data pro BI, full refresh
L2_citations             │
L2_answer_texts         ─┘
```

### Soubory

| Soubor | Co dělá |
|---|---|
| `src/rankscale_extract.py` | Krok 1 — stahuje data z API |
| `.github/workflows/extract.yml` | Automatické spouštění kroku 1 (6:30 UTC) |
| `sql/schema_raw.sql` | DDL pro raw_ tabulky (spustit jednorázově) |
| `sql/schema_l1.sql` | DDL pro L1_ tabulky (spustit jednorázově) |
| `sql/transform_l1.sql` | Krok 2 — vytvoří L1_ tabulky z raw_ |
| `sql/transform_l2.sql` | Krok 3 — vytvoří L2_ tabulky z L1_ |

---

## Kde najít popis datového modelu

| Co hledáš | Kde to najdeš |
|---|---|
| **Popis L1 tabulek** — sloupce, grainy, SQL příklady | `docs/l1_tables.md` |
| **Popis L2 tabulek** — sloupce, grainy, jak napojit BI | `docs/l2_tables.md` |
| **Popis API endpointů** — parametry, reálné response struktury, odchylky od dokumentace | `docs/rankscale-endpoints.md` |
| **Jak nastavit Looker Studio a Tableau** | `docs/report-setup.md` |
| **Byznys požadavky na report** | `docs/report.md` |
