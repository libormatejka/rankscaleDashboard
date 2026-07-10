-- ============================================================
-- Rankscale → BigQuery  |  Extract 2 — schéma všech tabulek
-- Projekt:  libor-matejkacz
-- Dataset:  RankScaleDashboard
-- ============================================================
-- Spustit jednorázově před prvním extractem.
-- Tabulky plní: src/rankscale_report_extract.py (L0)
--               sql/extract2/transform_report.sql (L1, L2)
-- ============================================================


-- ------------------------------------------------------------
-- L0_report_table  (L0 — APPEND každý ETL run)
-- Zdroj: POST /v1/metrics/report s filters.topicId per každý topic
-- Grain: brand × topic × snapshot_date × ETL run
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.L0_report_table`
(
  owning_brand_id  STRING,
  topic_id         STRING,
  topic_name       STRING,
  snapshot_date    TIMESTAMP,
  brand_name       STRING,
  is_own_brand     BOOL,
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
-- L1_report_topic_brand  (L1 — full refresh po každém extractu)
-- Grain: brand × topic × snapshot_date (deduplikováno)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.L1_report_topic_brand`
(
  owning_brand_id  STRING,
  topic_id         STRING,
  topic_name       STRING,
  snapshot_date    TIMESTAMP,
  brand_name       STRING,
  is_own_brand     BOOL,
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
-- L2_report_topic_brand  (L2 — full refresh po každém extractu)
-- Grain: brand × topic × snapshot_date
-- Přidává snapshot_week pro BI
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.L2_report_topic_brand`
(
  owning_brand_id  STRING,
  topic_id         STRING,
  topic_name       STRING,
  snapshot_date    DATE,
  snapshot_week    STRING,     -- ISO týden, např. '2026-28'
  brand_name       STRING,
  is_own_brand     BOOL,
  visibility_score FLOAT64,
  sentiment        FLOAT64,
  avg_position     FLOAT64,
  detection_rate   FLOAT64,
  top3             FLOAT64,
  mentions         INT64,
  citations        INT64,
  etl_loaded_at    TIMESTAMP
);
