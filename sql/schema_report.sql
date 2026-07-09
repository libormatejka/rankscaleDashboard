-- ============================================================
-- Rankscale → BigQuery  |  Report tabulky (Extract 2)
-- Projekt:  libor-matejkacz
-- Dataset:  RankScaleDashboard
-- ============================================================
-- Tabulky jsou plněny scriptem src/rankscale_report_extract.py.
-- Žádná transformační logika — data jsou 1:1 z Rankscale API.
--
-- Každý ETL run APPENDuje nové řádky — historická data zůstávají.
-- Sloupec etl_loaded_at říká kdy byl řádek stažen.
-- ============================================================


-- ------------------------------------------------------------
-- raw_report_topic_brand
-- Zdroj: POST /v1/metrics/report s filters.topicId per každý topic
-- Jeden řádek per brand (vlastní i competitor) per topic per snapshot_date per owning_brand per ETL run.
-- Tags = unikátní tagy agregované přes všechny search termy daného topicu.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.raw_report_topic_brand`
(
  owning_brand_id  STRING,     -- brand jehož monitoring volání provedlo
  topic_id         STRING,
  topic_name       STRING,
  tags             STRING,     -- JSON string unikátních tagů topicu, např. '["product-brand","top-funnel"]'
  snapshot_date    TIMESTAMP,  -- timestamp snapshotu z API (parallel array)
  brand_name       STRING,     -- vlastní brand nebo competitor
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
