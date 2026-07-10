-- ============================================================
-- Rankscale → BigQuery  |  Extract 3 — schéma všech tabulek
-- Projekt:  libor-matejkacz
-- Dataset:  RankScaleDashboard
-- ============================================================
-- Spustit jednorázově před prvním extractem.
-- Tabulky plní: src/rankscale_tag_extract.py (L0)
--               sql/extract3/transform_tag.sql (L1, L2)
-- ============================================================


-- ------------------------------------------------------------
-- L0_tag_table  (L0 — APPEND každý ETL run)
-- Zdroj: POST /v1/metrics/report s filters.tags per každý tag
-- Grain: brand × tag × snapshot_date × ETL run
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.L0_tag_table`
(
  owning_brand_id  STRING,
  tag              STRING,
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
-- L1_tag_brand  (L1 — full refresh po každém extractu)
-- Grain: brand × tag × snapshot_date (deduplikováno)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.L1_tag_brand`
(
  owning_brand_id  STRING,
  tag              STRING,
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
-- L2_tag_brand  (L2 — full refresh po každém extractu)
-- Grain: brand × tag × snapshot_date
-- Přidává snapshot_week pro BI
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.L2_tag_brand`
(
  owning_brand_id  STRING,
  tag              STRING,
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
