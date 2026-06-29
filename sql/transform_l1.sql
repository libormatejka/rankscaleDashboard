-- ============================================================
-- L1 tabulky — denní transformace z raw_ vrstvy
-- Projekt:  libor-matejkacz
-- Dataset:  RankScaleDashboard
-- ============================================================
-- Spouštět každý den PO dokončení raw extractu (rankscale_extract.py).
-- Každý příkaz je CREATE OR REPLACE → kompletní přepočet z raw dat.
-- Předpoklad: raw_ tabulky existují a jsou naplněny.
-- Schema tabulek: sql/schema_l1.sql
-- ============================================================


-- ── 1. L1_dim_brands ─────────────────────────────────────────────────────────
-- Grain: 1 řádek per brand_id
-- Logika: poslední known stav brandu z raw_brands
-- is_active = TRUE pokud brand byl součástí posledního ETL runu

CREATE OR REPLACE TABLE `libor-matejkacz.RankScaleDashboard.L1_dim_brands` AS
WITH ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY brand_id ORDER BY etl_loaded_at DESC) AS rn
  FROM `libor-matejkacz.RankScaleDashboard.raw_brands`
),
latest_run AS (
  SELECT MAX(DATE(etl_loaded_at)) AS d
  FROM `libor-matejkacz.RankScaleDashboard.raw_brands`
)
SELECT
  brand_id,
  name,
  domain,
  is_own_brand,
  DATE(etl_loaded_at) = (SELECT d FROM latest_run) AS is_active,
  etl_loaded_at AS updated_at
FROM ranked
WHERE rn = 1;


-- ── 2. L1_dim_search_terms ───────────────────────────────────────────────────
-- Grain: 1 řádek per search_term_id
-- Logika: poslední known stav promptu z raw_search_terms
-- is_active = status 'active' v posledním záznamu pro daný search_term_id

CREATE OR REPLACE TABLE `libor-matejkacz.RankScaleDashboard.L1_dim_search_terms` AS
WITH ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY search_term_id ORDER BY etl_loaded_at DESC) AS rn
  FROM `libor-matejkacz.RankScaleDashboard.raw_search_terms`
)
SELECT
  search_term_id,
  brand_id,
  query,
  engine,
  topic_id,
  topic_name,
  tags,
  region,
  `interval`,
  status = 'active' AS is_active,
  etl_loaded_at AS updated_at
FROM ranked
WHERE rn = 1;


-- ── 3. L1_fact_snapshots ─────────────────────────────────────────────────────
-- Grain: search_term × brand × snapshot_week
-- Logika: pro každou kombinaci vzít nejnovější Rankscale snapshot z daného týdne
-- ai_share_of_voice = podíl visibility vlastního brandu vůči všem brandům
--   v daném promptu a týdnu (NULL pro competitors)

CREATE OR REPLACE TABLE `libor-matejkacz.RankScaleDashboard.L1_fact_snapshots`
PARTITION BY snapshot_date
CLUSTER BY is_own_brand, engine
AS
WITH ranked AS (
  SELECT
    *,
    DATE(COALESCE(last_snapshot_at, etl_loaded_at))                                      AS snapshot_date,
    FORMAT_DATE('%G-%V', DATE(COALESCE(last_snapshot_at, etl_loaded_at)))                AS snapshot_week,
    ROW_NUMBER() OVER (
      PARTITION BY
        search_term_id,
        brand_name,
        FORMAT_DATE('%G-%V', DATE(COALESCE(last_snapshot_at, etl_loaded_at)))
      ORDER BY last_snapshot_at DESC, etl_loaded_at DESC
    ) AS rn
  FROM `libor-matejkacz.RankScaleDashboard.raw_brand_snapshots`
),
deduped AS (
  SELECT * FROM ranked WHERE rn = 1
)
SELECT
  snapshot_week,
  snapshot_date,
  search_term_id,
  brand_name,
  CASE WHEN is_own_brand THEN brand_id ELSE NULL END AS brand_id,  -- competitors nemají brand_id
  is_own_brand,
  topic_id,
  engine,
  visibility_score,
  avg_sentiment,
  avg_rank,
  latest_rank,
  detection_rate,
  top3_rate,
  citation_count,
  appearances,
  SAFE_DIVIDE(
    visibility_score,
    SUM(visibility_score) OVER (PARTITION BY search_term_id, snapshot_week)
  ) AS ai_share_of_voice
FROM deduped;


-- ── 4. L1_fact_citations ─────────────────────────────────────────────────────
-- Grain: brand × search_term × engine × domain × url × snapshot_week
-- Logika: citations nemají vlastní timestamp — snapshot_week se odvozuje z etl_loaded_at

CREATE OR REPLACE TABLE `libor-matejkacz.RankScaleDashboard.L1_fact_citations`
PARTITION BY snapshot_date
CLUSTER BY engine, domain
AS
WITH ranked AS (
  SELECT
    *,
    DATE(etl_loaded_at)                             AS snapshot_date,
    FORMAT_DATE('%G-%V', DATE(etl_loaded_at))       AS snapshot_week,
    ROW_NUMBER() OVER (
      PARTITION BY
        brand_id,
        search_term_id,
        engine,
        domain,
        IFNULL(url, ''),
        FORMAT_DATE('%G-%V', DATE(etl_loaded_at))
      ORDER BY etl_loaded_at DESC
    ) AS rn
  FROM `libor-matejkacz.RankScaleDashboard.raw_citations`
)
SELECT
  snapshot_week,
  snapshot_date,
  search_term_id,
  brand_id,
  engine,
  domain,
  url,
  occurrences
FROM ranked
WHERE rn = 1;


-- ── 5. L1_fact_answer_texts ───────────────────────────────────────────────────
-- Grain: execution_id (unikátní AI odpověď)
-- Logika: dedup podle execution_id, snapshot_week odvozeno z executed_at

CREATE OR REPLACE TABLE `libor-matejkacz.RankScaleDashboard.L1_fact_answer_texts`
PARTITION BY DATE(executed_at)
CLUSTER BY engine
AS
WITH ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY execution_id ORDER BY etl_loaded_at DESC) AS rn
  FROM `libor-matejkacz.RankScaleDashboard.raw_answer_texts`
)
SELECT
  execution_id,
  search_term_id,
  FORMAT_DATE('%G-%V', DATE(executed_at)) AS snapshot_week,
  executed_at,
  engine,
  answer_text
FROM ranked
WHERE rn = 1;
