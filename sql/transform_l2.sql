-- ============================================================
-- L2 tabulky — denormalizovaná vrstva připravená pro BI
-- Projekt:  libor-matejkacz
-- Dataset:  RankScaleDashboard
-- ============================================================
-- Spouštět každý den PO transform_l1.sql.
-- Všechny joiny jsou předpočítané — v BI nástroji žádné joiny.
-- ============================================================


-- ── 1. L2_snapshots ──────────────────────────────────────────────────────────
-- Hlavní tabulka pro všechny metriky. Nula joinů v BI nástroji.
-- Grain: search_term × brand × snapshot_week

CREATE OR REPLACE TABLE `libor-matejkacz.RankScaleDashboard.L2_snapshots`
PARTITION BY snapshot_date
CLUSTER BY is_own_brand, engine, topic_id
AS
SELECT
  -- časová dimenze
  s.snapshot_week,
  s.snapshot_date,

  -- prompt kontext (z dim_search_terms = aktuální stav promptu)
  s.search_term_id,
  st.query,
  st.region,
  st.`interval`                       AS refresh_interval,
  st.is_active                        AS is_search_term_active,

  -- topic (historický z snapshotu — platný v době měření)
  s.topic_id,
  st.topic_name,

  -- tagy (JSON string — pro filtr v BI použij L2_search_term_tags)
  st.tags,

  -- engine
  s.engine,

  -- brand kontext
  s.brand_name,
  s.brand_id,
  s.is_own_brand,

  -- metriky
  s.visibility_score,
  s.avg_sentiment,
  s.avg_rank,
  s.latest_rank,
  s.detection_rate,
  s.top3_rate,
  s.citation_count,
  s.appearances,
  s.ai_share_of_voice

FROM `libor-matejkacz.RankScaleDashboard.L1_fact_snapshots` s
LEFT JOIN `libor-matejkacz.RankScaleDashboard.L1_dim_search_terms` st
  ON s.search_term_id = st.search_term_id;


-- ── 2. L2_search_term_tags ───────────────────────────────────────────────────
-- Unnested tagy — 1 řádek per search_term × tag.
-- Použij pro filtrování L2_snapshots podle tagu:
--   JOIN L2_search_term_tags t ON t.search_term_id = s.search_term_id
--   WHERE t.tag = 'product-brand'

CREATE OR REPLACE TABLE `libor-matejkacz.RankScaleDashboard.L2_search_term_tags` AS
SELECT
  st.search_term_id,
  st.brand_id,
  st.topic_id,
  st.topic_name,
  st.engine,
  st.query,
  TRIM(tag) AS tag
FROM `libor-matejkacz.RankScaleDashboard.L1_dim_search_terms` st,
  UNNEST(JSON_VALUE_ARRAY(tags)) AS tag
WHERE tags IS NOT NULL
  AND tags NOT IN ('[]', 'null', '');


-- ── 3. L2_citations ──────────────────────────────────────────────────────────
-- Flat citace s kontextem promptu. Nula joinů v BI nástroji.
-- Grain: search_term × engine × domain × url × snapshot_week

CREATE OR REPLACE TABLE `libor-matejkacz.RankScaleDashboard.L2_citations`
PARTITION BY snapshot_date
CLUSTER BY engine, domain
AS
SELECT
  -- časová dimenze
  c.snapshot_week,
  c.snapshot_date,

  -- prompt kontext
  c.search_term_id,
  st.query,
  st.topic_id,
  st.topic_name,
  st.tags,

  -- brand kontext (čí monitoring citaci zachytil)
  c.brand_id,
  b.name  AS brand_name,

  -- engine
  c.engine,

  -- citace
  c.domain,
  c.url,
  c.occurrences

FROM `libor-matejkacz.RankScaleDashboard.L1_fact_citations` c
LEFT JOIN `libor-matejkacz.RankScaleDashboard.L1_dim_search_terms` st
  ON c.search_term_id = st.search_term_id
LEFT JOIN `libor-matejkacz.RankScaleDashboard.L1_dim_brands` b
  ON c.brand_id = b.brand_id;


-- ── 4. L2_answer_texts ───────────────────────────────────────────────────────
-- Flat texty AI odpovědí s kontextem promptu. Nula joinů v BI nástroji.
-- Grain: execution_id

CREATE OR REPLACE TABLE `libor-matejkacz.RankScaleDashboard.L2_answer_texts`
PARTITION BY DATE(executed_at)
CLUSTER BY engine
AS
SELECT
  -- identifikace
  a.execution_id,
  a.snapshot_week,
  a.executed_at,

  -- prompt kontext
  a.search_term_id,
  st.query,
  st.topic_id,
  st.topic_name,
  st.tags,

  -- engine
  a.engine,

  -- obsah
  a.answer_text

FROM `libor-matejkacz.RankScaleDashboard.L1_fact_answer_texts` a
LEFT JOIN `libor-matejkacz.RankScaleDashboard.L1_dim_search_terms` st
  ON a.search_term_id = st.search_term_id;
