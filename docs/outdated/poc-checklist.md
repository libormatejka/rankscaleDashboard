# POC Checklist – Rankscale → BigQuery pipeline

**Cíl:** Funkční denní ETL v GitHub Actions. Stahuje data z Rankscale API a nahrává do BigQuery.  
**Strategie:** Start malý, iterate. Každá fáze je nezávislá a testovatelná.

---

## Stav před startem

| Co existuje | Stav | Poznámka |
|---|---|---|
| `src/rankscale_etl.py` | ✅ Přepsáno | Správné field names, 4 kroky (brands, search-terms, snapshots, answer-texts) |
| `sql/schema_rankscale.sql` | ✅ Vytvořeno | Nové 4-tabulkové schéma odpovídající reálnému API |
| `requirements.txt` | ✅ OK | `requests`, `google-cloud-bigquery`, `google-auth` |
| GitHub Actions workflow | ✅ Existuje | `.github/workflows/etl.yml` – denně 6:00 UTC |
| BigQuery dataset | ✅ Tabulky vytvořeny | DDL spuštěno dle `schema_rankscale.sql` |
| GCP Service Account | ✅ Hotovo | Klíč uložen jako `GCP_SA_JSON` secret |
| GitHub Secrets | ✅ Hotovo | `RANKSCALE_API_KEY`, `GCP_SA_JSON`, `GCP_PROJECT`, `BQ_DATASET` |

---

## Fáze 1 – Setup infrastruktury
*Jednorázová příprava před vším ostatním. Dělá se ručně v konzoli.*

- [ ] **1.1** Ověřit nebo vytvořit BigQuery dataset  
  → GCP Console → BigQuery → projekt `libor-matejkacz` → Create dataset `RankScaleDashboard`  
  → Region: `EU` nebo `US` (zvol jednou, nejde měnit)

- [ ] **1.2** Vytvořit GCP Service Account pro GitHub Actions  
  → IAM → Service Accounts → Create  
  → Role: `BigQuery Data Editor` + `BigQuery Job User`  
  → Stáhnout JSON klíč

- [ ] **1.3** Přidat GitHub Secrets do repozitáře  
  → Settings → Secrets and variables → Actions → New repository secret  
  ```
  RANKSCALE_API_KEY  = rk_...
  GCP_SA_JSON        = { celý obsah JSON klíče }
  GCP_PROJECT        = libor-matejkacz
  BQ_DATASET         = RankScaleDashboard
  RANKSCALE_BRAND_ID = E5GAVmqco65u7Smx3hso
  ```

- [ ] **1.4** Ověřit API klíč Rankscale  
  ```bash
  curl -H "Authorization: Bearer rk_..." \
    "https://rankscale.ai/v1/metrics/brands"
  ```

---

## Fáze 2 – BigQuery schéma (nové, Rankscale-nativní)
*Zahodit původní schema.sql a vytvořit tabulky odpovídající reálné API struktuře.*

Proč nové schéma místo původního? Původní 4-tabulková struktura (brands → prompts → prompt_runs → run_metrics) byla navržena pro DIY přístup. Pro Rankscale SaaS data jsou přirozenější flat tabulky se snímky (snapshots).

### Navrhované tabulky POC

```
dim_brands           – číselník brandů (vlastní + competitors)
dim_search_terms     – číselník search termů s tématem a enginem  
fact_brand_snapshots – týdenní snapshot metrik per brand per search term  ← HLAVNÍ TABULKA
fact_answer_texts    – raw AI odpovědi (volitelné, pro LLM analýzy)
```

- [ ] **2.1** Vytvořit nové `sql/schema_rankscale.sql` s DDL pro 4 tabulky  
  *(kód viz sekce Appendix níže)*

- [ ] **2.2** Spustit DDL v BigQuery Console  
  → BigQuery → Query editor → vložit a spustit `schema_rankscale.sql`

- [ ] **2.3** Ověřit že tabulky existují a mají správné sloupce

---

## Fáze 3 – Oprava ETL skriptu
*Existující `src/rankscale_etl.py` je potřeba přepsat – má špatné field mappings.*

### Co je špatně v současném skriptu

| Krok | Problém | Správně |
|---|---|---|
| `step_report` | Čte `timeSeries`, `byEngine` | Tyto klíče **neexistují** v reálném API |
| `step_search_term_snapshots` | Čte `latestRun`, `trend` | Tyto klíče **neexistují** v reálném API |
| `step_sentiment` | Čte `timeSeries` ze sentimentu | Sentiment vrací `brandSentiments[]`, ne timeSeries |
| `step_citations` | Stránkuje přes offset | Citations používá **cap model**, ne offset |
| `api_post_paginated` | Předpokládá `pagination.hasMore` | Struktura je `paginationInfo.hasMore` |
| `step_brands` | Čte `brands[0]["id"]` | Reálný klíč je `brands[0]["id"]` ✅ ale struktura neověřena |

### Minimální POC scope (3 kroky místo 7)

Pro POC stačí:
1. `step_brands` → `dim_brands`
2. `step_search_terms` → `dim_search_terms`  
3. `step_brand_snapshots` → `fact_brand_snapshots` ← nový, nahrazuje kroky 3+4

Sentiment a citations přidáme ve fázi 4+.

- [ ] **3.1** Přepsat `step_brands` – ověřit reálné field names z `endpoint-brand.json`

- [ ] **3.2** Přepsat `step_search_terms` – ověřit reálné field names z `endpoint-search-terms.json`

- [ ] **3.3** Napsat nový `step_brand_snapshots` z `POST /v1/metrics/search-terms-report`  
  Logika:  
  - Pro každý search term: extrahuj `ownBrand` (pokud existuje) + každý `competitors[]` záznam  
  - Jeden řádek = jeden brand × jeden search term × jeden týdenní snapshot  
  - `snapshot_week` = ISO week (YYYY-WW) odvozený z `lastSnapshotAt`  
  - Metriky: `visibility_score`, `avg_sentiment`, `avg_rank`, `detection_rate`, `top3_rate`, `citation_count`

- [ ] **3.4** Přidat `--dry-run` mode pro lokální testování (tiskne co by se nahrálo, ale nepíše do BQ)

- [ ] **3.5** Lokálně otestovat skript s reálnými credentials  
  ```bash
  export RANKSCALE_API_KEY=rk_...
  export GCP_PROJECT=libor-matejkacz
  export RANKSCALE_BRAND_ID=E5GAVmqco65u7Smx3hso
  python src/rankscale_etl.py --dry-run
  ```

---

## Fáze 4 – GitHub Actions workflow
*Automatizace: skript se spustí každý den automaticky.*

- [ ] **4.1** Vytvořit `.github/workflows/etl.yml`  
  ```yaml
  name: Rankscale ETL
  
  on:
    schedule:
      - cron: '0 6 * * *'   # každý den v 6:00 UTC
    workflow_dispatch:        # manuální spuštění přes GitHub UI
  
  jobs:
    etl:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        
        - uses: actions/setup-python@v5
          with:
            python-version: '3.12'
            cache: pip
        
        - run: pip install -r requirements.txt
        
        - name: Run ETL
          env:
            RANKSCALE_API_KEY:  ${{ secrets.RANKSCALE_API_KEY }}
            GCP_SA_JSON:        ${{ secrets.GCP_SA_JSON }}
            GCP_PROJECT:        ${{ secrets.GCP_PROJECT }}
            BQ_DATASET:         ${{ secrets.BQ_DATASET }}
            RANKSCALE_BRAND_ID: ${{ secrets.RANKSCALE_BRAND_ID }}
          run: python src/rankscale_etl.py
  ```

- [ ] **4.2** Pushnut workflow do GitHubu

- [ ] **4.3** Spustit manuálně (Actions → workflow → Run workflow) a ověřit logy

- [ ] **4.4** Ověřit data v BigQuery po prvním úspěšném runu

---

## Fáze 5 – První datový load
*Po funkčním pipeline: naplnit historická data.*

- [ ] **5.1** Spustit jednorázový historický load s `timeFrame: 3m`  
  → Přidat CLI parametr nebo env var `TIME_FRAME=3m` na jeden run  
  → Tím naplníš ~12 týdnů historie

- [ ] **5.2** Ověřit v BigQuery:
  ```sql
  -- Kolik snapshots per týden?
  SELECT snapshot_week, COUNT(*) as rows
  FROM `libor-matejkacz.RankScaleDashboard.fact_brand_snapshots`
  GROUP BY snapshot_week ORDER BY snapshot_week;
  
  -- Vlastní brand vs competitors?
  SELECT is_own_brand, COUNT(DISTINCT brand_name) as brands, COUNT(*) as rows
  FROM `libor-matejkacz.RankScaleDashboard.fact_brand_snapshots`
  GROUP BY is_own_brand;
  ```

- [ ] **5.3** Přepnout na inkrementální `timeFrame: 7d` pro denní runy

---

## Fáze 6 – Iterace (po funkčním POC)
*Přidávat postupně, ne vše najednou.*

- [ ] **6.1** Přidat `fact_answer_texts` – raw AI odpovědi pro LLM analýzy
- [ ] **6.2** Přidat `fact_sentiment_keywords` – keyword breakdown ze sentimentu
- [ ] **6.3** Přidat normalizaci competitor názvů (`MONETA` → `MONETA Money Bank`)
- [ ] **6.4** Přidat alert na vyčerpání kreditů (GET /v1/metrics/credits)
- [ ] **6.5** Napojit Tableau / Looker Studio na `fact_brand_snapshots`
- [ ] **6.6** Přidat monitoring: GitHub Actions notifikace při selhání

---

## Appendix: DDL pro nové schéma

```sql
-- ============================================================
-- Rankscale-native schema (POC)
-- Dataset: libor-matejkacz.RankScaleDashboard
-- ============================================================

-- Číselník brandů (vlastní + sledovaní competitors)
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.dim_brands` (
  brand_id          STRING    NOT NULL,
  name              STRING    NOT NULL,
  domain            STRING,
  is_own_brand      BOOL,
  search_term_count INT64,
  loaded_at         TIMESTAMP
);

-- Číselník search termů (query × engine kombinace)
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.dim_search_terms` (
  search_term_id  STRING    NOT NULL,   -- Rankscale searchTermId
  brand_id        STRING    NOT NULL,
  query           STRING    NOT NULL,   -- text promptu
  topic_id        STRING,               -- Rankscale topic ID
  topic_name      STRING,               -- "Brand", "Půjčky/Úvěry", "Investice"
  engine          STRING,               -- "google_ai_mode_gui" atd.
  region          STRING,               -- "cz"
  interval        STRING,               -- "weekly"
  tags            JSON,                 -- pole tagů
  is_active       BOOL,
  loaded_at       TIMESTAMP
);

-- Hlavní fact tabulka: týdenní snapshot per brand per search term
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.fact_brand_snapshots`
(
  snapshot_date    DATE      NOT NULL,  -- datum ETL runu (PARTITION key)
  snapshot_week    STRING    NOT NULL,  -- ISO týden, např. "2026-21"
  search_term_id   STRING    NOT NULL,
  brand_name       STRING    NOT NULL,
  is_own_brand     BOOL      NOT NULL,
  brand_id         STRING,              -- NULL pokud brand není v dim_brands

  -- Metriky (vše v původní Rankscale škále, bez rescalování)
  visibility_score  FLOAT64,            -- 0–100
  avg_sentiment     FLOAT64,            -- 0–100 (50 = neutrální)
  avg_rank          FLOAT64,            -- 1–N (null = nedetekován)
  latest_rank       INT64,              -- rank v posledním snapshotu
  detection_rate    FLOAT64,            -- 0–100 %
  top3_rate         FLOAT64,            -- 0–100 %
  citation_count    INT64,
  appearances       INT64,              -- počet snapshotů kde se brand objevil

  -- Metadata
  last_snapshot_at  TIMESTAMP,
  topic_name        STRING,             -- denorm. pro pohodlí v SQL
  engine            STRING,             -- denorm. pro pohodlí v SQL
  loaded_at         TIMESTAMP
)
PARTITION BY snapshot_date
CLUSTER BY is_own_brand, topic_name, engine;

-- Raw AI odpovědi (volitelné, velká data)
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.fact_answer_texts`
(
  execution_id    STRING    NOT NULL,
  search_term_id  STRING    NOT NULL,
  executed_at     TIMESTAMP NOT NULL,   -- PARTITION key
  engine          STRING,
  query           STRING,
  topic_name      STRING,
  answer_text     STRING,               -- plný markdown text odpovědi AI
  loaded_at       TIMESTAMP
)
PARTITION BY DATE(executed_at)
CLUSTER BY engine;
```

---

## Appendix: Klíčové field mappings (reálné API → BQ)

```
POST /v1/metrics/search-terms-report
└── data.searchTerms[]
    ├── searchTermId          → search_term_id
    ├── query                 → query
    ├── topic.id              → topic_id
    ├── topic.name            → topic_name
    ├── aiSearchEngines[0]    → engine
    ├── lastSnapshotAt        → last_snapshot_at
    │
    ├── ownBrand{}            → is_own_brand = TRUE
    │   ├── name              → brand_name
    │   ├── visibilityScore   → visibility_score
    │   ├── avgSentiment      → avg_sentiment
    │   ├── avgRank           → avg_rank
    │   ├── latestRank        → latest_rank
    │   ├── detectionRate     → detection_rate
    │   ├── top3              → top3_rate
    │   ├── citationCount     → citation_count
    │   └── appearances       → appearances
    │
    └── competitors[]         → is_own_brand = FALSE (jeden řádek per competitor)
        └── (stejná struktura jako ownBrand)
```
