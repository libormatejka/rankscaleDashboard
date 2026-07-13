-- ============================================================
-- Rankscale → BigQuery  |  Extract 2 — schéma tabulek
-- Projekt:  libor-matejkacz
-- Dataset:  RankScaleDashboard
-- ============================================================
-- Spustit jednorázově před prvním extractem.
-- Tabulky plní: src/rankscale_report_extract.py
-- ============================================================


-- ------------------------------------------------------------
-- L0_report_table  (L0 — APPEND každý ETL run)
-- Grain: brand × topic × snapshot_date × ETL run
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.L0_report_table`
(
  unique_row_id    STRING,
  business_key     STRING,
  owning_brand_id  STRING,
  topic_id         STRING,
  topic_name       STRING,
  snapshot_time    TIMESTAMP,
  snapshot_date    DATE,
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
