-- ============================================================
-- L1 tabulky — DDL
-- Projekt:  libor-matejkacz
-- Dataset:  RankScaleDashboard
-- ============================================================
-- Spusť jednorázově pro inicializaci tabulek.
-- Denní plnění: sql/transform_l1.sql
-- ============================================================


-- ------------------------------------------------------------
-- L1_dim_brands
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.L1_dim_brands`
(
  brand_id      STRING,
  name          STRING,
  domain        STRING,
  is_own_brand  BOOL,
  is_active     BOOL,    -- FALSE = brand smazán v Rankscale (chybí v posledním ETL runu)
  updated_at    TIMESTAMP
);


-- ------------------------------------------------------------
-- L1_dim_search_terms
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.L1_dim_search_terms`
(
  search_term_id  STRING,
  brand_id        STRING,   -- FK → L1_dim_brands
  query           STRING,   -- text promptu
  engine          STRING,   -- "chatgpt_gui" | "google_ai_mode_gui" | ...
  topic_id        STRING,
  topic_name      STRING,   -- "Půjčky" | "Hypotéky" | "Investice" | ...
  tags            STRING,   -- JSON string, např. '["top-funnel","segment-a"]'
  region          STRING,
  `interval`      STRING,   -- "weekly" | "daily"
  is_active       BOOL,     -- FALSE = prompt vypnut nebo smazán
  updated_at      TIMESTAMP
);


-- ------------------------------------------------------------
-- L1_fact_snapshots  ← hlavní tabulka reportu
-- Grain: search_term × brand × snapshot_week
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.L1_fact_snapshots`
(
  snapshot_week       STRING,    -- ISO week "2026-26"
  snapshot_date       DATE,      -- datum Rankscale snapshotu (PARTITION key)
  search_term_id      STRING,    -- FK → L1_dim_search_terms
  brand_name          STRING,    -- název brandu (vlastní i competitor)
  brand_id            STRING,    -- FK → L1_dim_brands (NULL pro competitors)
  is_own_brand        BOOL,
  topic_id            STRING,    -- topic platný v době snapshotu
  engine              STRING,
  visibility_score    FLOAT64,   -- 0–100
  avg_sentiment       FLOAT64,   -- 0–100
  avg_rank            FLOAT64,   -- průměrná pozice (1 = nejlepší)
  latest_rank         INT64,     -- pozice v posledním snapshotu
  detection_rate      FLOAT64,   -- 0–100 %
  top3_rate           FLOAT64,   -- 0–100 %
  citation_count      INT64,
  appearances         INT64,
  ai_share_of_voice   FLOAT64    -- visibility vlastního brandu / suma všech brandů v daném promptu a týdnu
)
PARTITION BY snapshot_date
CLUSTER BY is_own_brand, engine;


-- ------------------------------------------------------------
-- L1_fact_citations
-- Grain: search_term × engine × domain × url × snapshot_week
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.L1_fact_citations`
(
  snapshot_week   STRING,
  snapshot_date   DATE,      -- PARTITION key
  search_term_id  STRING,    -- FK → L1_dim_search_terms
  brand_id        STRING,    -- FK → L1_dim_brands (čí brand monitoring citaci zahrnul)
  engine          STRING,
  domain          STRING,    -- citovaná doména, např. "banky.cz"
  url             STRING,    -- konkrétní URL
  occurrences     INT64
)
PARTITION BY snapshot_date
CLUSTER BY engine, domain;


-- ------------------------------------------------------------
-- L1_fact_answer_texts
-- Grain: execution_id (unikátní AI odpověď)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.L1_fact_answer_texts`
(
  execution_id    STRING,    -- PK
  search_term_id  STRING,    -- FK → L1_dim_search_terms
  snapshot_week   STRING,
  executed_at     TIMESTAMP, -- PARTITION key
  engine          STRING,
  answer_text     STRING
)
PARTITION BY DATE(executed_at)
CLUSTER BY engine;
