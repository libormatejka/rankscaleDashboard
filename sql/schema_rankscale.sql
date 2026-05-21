-- ============================================================
-- Rankscale → BigQuery schema (POC)
-- Projekt:  libor-matejkacz
-- Dataset:  RankScaleDashboard
-- ============================================================
-- Spusť celý soubor v BigQuery Console (Query editor).
-- Všechny příkazy jsou idempotentní (CREATE TABLE IF NOT EXISTS).
-- ============================================================


-- ------------------------------------------------------------
-- 1. dim_brands
-- Zdroj: GET /v1/metrics/brands
-- Strategie: WRITE_TRUNCATE (malá tabulka, každý den se přepíše)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.dim_brands` (
  brand_id          STRING    NOT NULL,   -- Rankscale brand ID
  name              STRING    NOT NULL,   -- název brandu
  domain            STRING,               -- doména (pokud dostupná)
  is_own_brand      BOOL,                 -- true = vlastní brand
  search_term_count INT64,                -- počet sledovaných search termů
  loaded_at         TIMESTAMP             -- čas posledního ETL runu
);


-- ------------------------------------------------------------
-- 2. dim_search_terms
-- Zdroj: GET /v1/metrics/search-terms
-- Strategie: WRITE_TRUNCATE (malá tabulka, každý den se přepíše)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.dim_search_terms` (
  search_term_id  STRING    NOT NULL,   -- Rankscale searchTermId (query × engine)
  brand_id        STRING    NOT NULL,   -- FK → dim_brands.brand_id
  query           STRING    NOT NULL,   -- text promptu posílaného AI enginu
  topic_id        STRING,               -- Rankscale topic ID
  topic_name      STRING,               -- "Brand" | "Půjčky/Úvěry" | "Investice"
  engine          STRING,               -- "google_ai_mode_gui" | "chatgpt_gui" | ...
  region          STRING,               -- "cz" | "sk" | ...
  interval        STRING,               -- "weekly" | "daily"
  tags            JSON,                 -- pole tagů z Rankscale
  is_active       BOOL,                 -- true = aktivní search term
  loaded_at       TIMESTAMP
);


-- ------------------------------------------------------------
-- 3. fact_brand_snapshots          ← HLAVNÍ TABULKA
-- Zdroj: POST /v1/metrics/search-terms-report
-- Strategie: PARTITION OVERWRITE per snapshot_date
--
-- Jeden řádek = jeden brand × jeden search term × jeden týden.
-- Obsahuje vlastní brand (is_own_brand = TRUE) i konkurenty.
-- Kumuluje se každý týden → základ pro time-series reporting.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.fact_brand_snapshots`
(
  -- Identifikace
  snapshot_date    DATE      NOT NULL,  -- datum ETL runu (PARTITION key)
  snapshot_week    STRING    NOT NULL,  -- ISO week, např. "2026-21"
  search_term_id   STRING    NOT NULL,  -- FK → dim_search_terms.search_term_id
  brand_name       STRING    NOT NULL,  -- název brandu (může být neznámý competitor)
  is_own_brand     BOOL      NOT NULL,  -- true = vlastní brand
  brand_id         STRING,              -- FK → dim_brands (NULL pro nesledované competitory)

  -- Rankscale metriky (v původní škále bez rescalování)
  visibility_score  FLOAT64,   -- 0–100; jak prominentně AI brand zmiňuje
  avg_sentiment     FLOAT64,   -- 0–100; 50 = neutrální, >50 pozitivní, <50 negativní
  avg_rank          FLOAT64,   -- průměrná pozice v AI odpovědi (1 = nejlepší); NULL = nedetekován
  latest_rank       INT64,     -- rank v posledním snapshotu; NULL = v posledním kole nenalezen
  detection_rate    FLOAT64,   -- 0–100; % snapshotů kde byl brand detekován
  top3_rate         FLOAT64,   -- 0–100; % výskytů na pozici 1–3
  citation_count    INT64,     -- počet URL citací tohoto brandu
  appearances       INT64,     -- počet snapshotů kde se brand objevil v daném období

  -- Denormalizace pro pohodlí (bez JOIN v Tableau/Looker)
  query             STRING,    -- text promptu
  topic_name        STRING,    -- "Brand" | "Půjčky/Úvěry" | "Investice"
  engine            STRING,    -- "google_ai_mode_gui" | ...
  last_snapshot_at  TIMESTAMP, -- kdy proběhl poslední Rankscale snapshot

  loaded_at         TIMESTAMP  -- čas ETL runu
)
PARTITION BY snapshot_date
CLUSTER BY is_own_brand, topic_name, engine;


-- ------------------------------------------------------------
-- 4. fact_answer_texts
-- Zdroj: POST /v1/metrics/search-terms-report (includeAnswerTexts: true)
-- Strategie: APPEND + dedup podle execution_id
--
-- Raw texty AI odpovědí. Ukládají se jednou (execution_id je unikátní).
-- Velká tabulka — spouštět méně často (týdně stačí).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.fact_answer_texts`
(
  execution_id    STRING    NOT NULL,   -- Rankscale executionId (unikátní navždy)
  search_term_id  STRING    NOT NULL,   -- FK → dim_search_terms
  executed_at     TIMESTAMP NOT NULL,   -- kdy AI engine odpověděl (PARTITION key)
  engine          STRING,               -- "google_ai_mode_gui" | ...
  query           STRING,               -- text promptu
  topic_name      STRING,               -- denorm.
  answer_text     STRING,               -- plný markdown text AI odpovědi
  loaded_at       TIMESTAMP
)
PARTITION BY DATE(executed_at)
CLUSTER BY engine;
