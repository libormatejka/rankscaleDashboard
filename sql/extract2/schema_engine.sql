-- ============================================================
-- Rankscale → BigQuery  |  Extract 2 — engine schéma
-- Projekt:  libor-matejkacz
-- Dataset:  RankScaleDashboard
-- ============================================================
-- Spustit jednorázově před prvním extractem.
-- Pouze vlastní brand — API nevrací engine breakdown pro competitors.
-- ============================================================


-- ------------------------------------------------------------
-- L0_report_engine  (L0 — APPEND každý ETL run)
-- Grain: owning_brand × topic × engine × snapshot_date × ETL run
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.L0_report_engine`
(
  owning_brand_id  STRING,
  topic_id         STRING,
  topic_name       STRING,
  engine_id        STRING,
  snapshot_date    TIMESTAMP,
  brand_name       STRING,
  visibility_score FLOAT64,
  sentiment        FLOAT64,
  avg_position     FLOAT64,
  detection_rate   FLOAT64,
  top3             FLOAT64,
  mentions         INT64,
  citations        INT64,
  etl_loaded_at    TIMESTAMP
);


-- ------------------------------------------------------------
-- L1_report_engine  (L1 — full refresh po každém extractu)
-- Grain: owning_brand × topic × engine × snapshot_date (deduplikováno)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.L1_report_engine`
(
  owning_brand_id  STRING,
  topic_id         STRING,
  topic_name       STRING,
  engine_id        STRING,
  snapshot_date    TIMESTAMP,
  brand_name       STRING,
  visibility_score FLOAT64,
  sentiment        FLOAT64,
  avg_position     FLOAT64,
  detection_rate   FLOAT64,
  top3             FLOAT64,
  mentions         INT64,
  citations        INT64,
  etl_loaded_at    TIMESTAMP
);


-- ------------------------------------------------------------
-- L2_report_engine  (L2 — full refresh po každém extractu)
-- Grain: owning_brand × topic × engine × snapshot_date
-- Přidává snapshot_week pro BI
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.L2_report_engine`
(
  owning_brand_id  STRING,
  topic_id         STRING,
  topic_name       STRING,
  engine_id        STRING,
  snapshot_date    DATE,
  snapshot_week    STRING,
  brand_name       STRING,
  visibility_score FLOAT64,
  sentiment        FLOAT64,
  avg_position     FLOAT64,
  detection_rate   FLOAT64,
  top3             FLOAT64,
  mentions         INT64,
  citations        INT64,
  etl_loaded_at    TIMESTAMP
);
