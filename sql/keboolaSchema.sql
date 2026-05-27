-- ============================================================
-- AI Visibility Dashboard — Snowflake Reporting Schema
-- Target: Snowflake (výstup Keboola transformace)
--
-- Zdroj L0:  BigQuery (schema_rankscale.sql)
-- Transformace: Keboola
--
-- Schéma je tool-agnostické — nezávisí na Rankscale API struktuře.
-- Při změně nástroje se změní jen Keboola transformace, ne toto schéma.
-- ============================================================


-- ------------------------------------------------------------
-- 1. dim_brands
-- Vlastní brand + detekovaní konkurenti.
-- Keboola zdroj: BQ dim_brands + unikátní brand_name z fact_brand_snapshots
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_brands (
  brand_id     VARCHAR     NOT NULL,   -- Rankscale brand_id (nebo generated pro competitors)
  brand_name   VARCHAR     NOT NULL,
  entity_type  VARCHAR     NOT NULL,   -- OWN_BRAND | COMPETITOR
  domain       VARCHAR,
  loaded_at    TIMESTAMP_NTZ
);


-- ------------------------------------------------------------
-- 2. dim_prompts
-- Jeden řádek = jeden dotaz × jeden AI engine × region.
-- topic je normalizován do EN (Brand → brand, Půjčky/Úvěry → loans, Investice → investments).
-- Keboola zdroj: BQ dim_search_terms
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_prompts (
  prompt_id    VARCHAR     NOT NULL,   -- = search_term_id z Rankscale
  prompt_text  VARCHAR     NOT NULL,   -- text dotazu posílaného AI enginu
  topic        VARCHAR,                -- brand | loans | investments
  ai_engine    VARCHAR,                -- chatgpt | google_ai_mode | perplexity | ...
  region       VARCHAR,                -- cz | sk | ...
  is_active    BOOLEAN,
  loaded_at    TIMESTAMP_NTZ
);


-- ------------------------------------------------------------
-- 3. fact_ai_visibility         ← HLAVNÍ REPORTOVACÍ TABULKA
-- Jeden řádek = brand × prompt × týdenní snapshot.
-- Obsahuje vlastní brand i konkurenty.
-- Keboola zdroj: BQ fact_brand_snapshots
--
-- CLUSTER BY entity_type, topic, ai_engine
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_ai_visibility (
  snapshot_date    DATE        NOT NULL,  -- datum snapshotu (partition/cluster key)
  snapshot_week    VARCHAR     NOT NULL,  -- ISO týden, např. "2026-21"
  prompt_id        VARCHAR     NOT NULL,  -- FK → dim_prompts
  brand_id         VARCHAR,               -- FK → dim_brands (NULL pro nesledované competitory)
  brand_name       VARCHAR     NOT NULL,  -- denorm. pro Tableau (bez JOIN)
  entity_type      VARCHAR     NOT NULL,  -- OWN_BRAND | COMPETITOR

  -- Metriky (v původní Rankscale škále, přepočet lze udělat v Tableau/dbt)
  visibility_score NUMBER(6,2),           -- 0–100
  sentiment_score  NUMBER(6,2),           -- 0–100 (50 = neutrální)
  avg_rank         NUMBER(6,2),           -- 1–N; NULL = brand nebyl detekován
  detection_rate   NUMBER(6,2),           -- 0–100 %
  top3_rate        NUMBER(6,2),           -- 0–100 %
  citation_count   NUMBER,
  appearances      NUMBER,

  -- Kontext pro filtrování v Tableau (denorm. bez JOIN)
  topic            VARCHAR,               -- brand | loans | investments
  ai_engine        VARCHAR,               -- chatgpt | google_ai_mode | perplexity | ...
  region           VARCHAR,

  loaded_at        TIMESTAMP_NTZ
)
CLUSTER BY (snapshot_date, entity_type, topic, ai_engine);


-- ------------------------------------------------------------
-- 4. fact_answer_texts          ← VOLITELNÉ (pro LLM analýzy)
-- Raw texty AI odpovědí. Slouží pro vlastní NLP analýzy mimo Tableau.
-- Keboola zdroj: BQ fact_answer_texts
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_answer_texts (
  execution_id  VARCHAR     NOT NULL,   -- unikátní ID execuce (dedup key)
  prompt_id     VARCHAR     NOT NULL,   -- FK → dim_prompts
  executed_at   TIMESTAMP_NTZ NOT NULL,
  ai_engine     VARCHAR,
  prompt_text   VARCHAR,
  topic         VARCHAR,
  answer_text   VARCHAR,                -- plný markdown text AI odpovědi
  loaded_at     TIMESTAMP_NTZ
)
CLUSTER BY (executed_at, ai_engine);
