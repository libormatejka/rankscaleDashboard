-- ============================================================
-- AI SEO Dashboard — BigQuery Schema
-- Dataset: libor-matejkacz.RankScaleDashboard
-- ============================================================

-- ------------------------------------------------------------
-- 1. brands
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.brands` (
  brand_id    STRING    NOT NULL,
  brand_name  STRING    NOT NULL,
  entity_type STRING    NOT NULL,   -- OWN_BRAND | COMPETITOR
  website     STRING,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

-- ------------------------------------------------------------
-- 2. prompts
-- Kategorie jsou přímé sloupce — hodnoty jsou fixní a známé předem.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.prompts` (
  prompt_id   STRING    NOT NULL,
  prompt_text STRING    NOT NULL,
  brand_id    STRING    NOT NULL,   -- FK → brands.brand_id

  -- Kategorie
  product     STRING    NOT NULL,   -- brand | loan | hypo
  source      STRING    NOT NULL,   -- SEO | Survey | Community | Custom
  segment     STRING,               -- hodnoty nebyly specifikovány
  funnel      STRING    NOT NULL,   -- See | Think | Do | Care
  type        STRING    NOT NULL,   -- inform | transaction

  is_active   BOOL      NOT NULL DEFAULT TRUE,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

-- ------------------------------------------------------------
-- 3. prompt_runs
-- PARTITION BY DATE(executed_at)
-- CLUSTER BY ai_provider, ai_model
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.prompt_runs` (
  run_id          STRING    NOT NULL,
  prompt_id       STRING    NOT NULL,   -- FK → prompts.prompt_id
  executed_at     TIMESTAMP NOT NULL,
  ai_model        STRING    NOT NULL,
  ai_provider     STRING    NOT NULL,   -- openai | anthropic | google
  response_text   STRING,
  prompt_snapshot STRING,
  input_tokens    INT64,
  output_tokens   INT64
)
PARTITION BY DATE(executed_at)
CLUSTER BY ai_provider, ai_model;

-- ------------------------------------------------------------
-- 4. run_metrics
-- PARTITION BY DATE(computed_at)
-- CLUSTER BY metric_type
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.run_metrics` (
  metric_id      STRING    NOT NULL,
  run_id         STRING    NOT NULL,   -- FK → prompt_runs.run_id
  metric_type    STRING    NOT NULL,   -- VISIBILITY | SENTIMENT | BRAND_MENTION | POSITION_RANK | RECOMMENDATION
  metric_value   FLOAT64   NOT NULL,
  metric_label   STRING,              -- POSITIVE | NEUTRAL | NEGATIVE (jen pro SENTIMENT)
  metric_details JSON,
  computed_at    TIMESTAMP NOT NULL
)
PARTITION BY DATE(computed_at)
CLUSTER BY metric_type;
