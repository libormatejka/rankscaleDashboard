-- ============================================================
-- Rankscale → BigQuery  |  Raw tabulky (L0 landing zone)
-- Projekt:  libor-matejkacz
-- Dataset:  RankScaleDashboard
-- ============================================================
-- Tabulky jsou plněny scriptem src/rankscale_extract.py.
-- Žádná transformační logika — data jsou 1:1 z Rankscale API.
-- Transformace (dedup, SCD, is_active, joiny) patří do Kebooly.
--
-- Každý ETL run APPENDuje nové řádky — historická data zůstávají.
-- Sloupec etl_loaded_at říká kdy byl řádek stažen.
-- ============================================================


-- ------------------------------------------------------------
-- raw_brands
-- Zdroj: GET /v1/metrics/brands
-- Jeden řádek per brand per ETL run.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.raw_brands`
(
  brand_id      STRING,
  name          STRING,
  domain        STRING,
  is_own_brand  BOOL,
  etl_loaded_at TIMESTAMP
);


-- ------------------------------------------------------------
-- raw_search_terms
-- Zdroj: GET /v1/metrics/search-terms
-- Jeden řádek per search term (prompt × engine) per brand per ETL run.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.raw_search_terms`
(
  brand_id            STRING,
  search_term_id      STRING,
  query               STRING,
  engine              STRING,
  topic_id            STRING,
  topic_name          STRING,
  region              STRING,
  `interval`          STRING,
  tags                STRING,    -- JSON string, např. '["dip","investice"]'
  status              STRING,    -- "active" | "inactive"
  created_at          TIMESTAMP,
  last_execution_time TIMESTAMP,
  next_execution_time TIMESTAMP,
  executions_amount   INT64,
  etl_loaded_at       TIMESTAMP
);


-- ------------------------------------------------------------
-- raw_brand_snapshots
-- Zdroj: POST /v1/metrics/search-terms-report
-- Jeden řádek per brand (vlastní i competitor) per search term per ETL run.
-- Keboola zde doplní dedup, snapshot_date, snapshot_week.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.raw_brand_snapshots`
(
  brand_id          STRING,
  search_term_id    STRING,
  engine            STRING,
  topic_id          STRING,
  topic_name        STRING,
  last_snapshot_at  TIMESTAMP,
  brand_name        STRING,
  is_own_brand      BOOL,
  visibility_score  FLOAT64,
  avg_sentiment     FLOAT64,
  avg_rank          FLOAT64,
  latest_rank       INT64,
  detection_rate    FLOAT64,
  top3_rate         FLOAT64,
  citation_count    INT64,
  appearances       INT64,
  etl_loaded_at     TIMESTAMP
);


-- ------------------------------------------------------------
-- raw_answer_texts
-- Zdroj: POST /v1/metrics/search-terms-report (includeAnswerTexts: true)
-- Jeden řádek per AI exekuce per brand per ETL run.
-- Keboola zde doplní dedup podle execution_id.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.raw_answer_texts`
(
  brand_id       STRING,
  search_term_id STRING,
  execution_id   STRING,
  executed_at    TIMESTAMP,
  engine         STRING,
  answer_text    STRING,
  etl_loaded_at  TIMESTAMP
);


-- ------------------------------------------------------------
-- raw_report_brand
-- Zdroj: POST /v1/metrics/report → historicalData + competitorTimeSeriesData
-- Jeden řádek per brand (vlastní i competitor) per snapshot_date per owning_brand per ETL run.
-- API samo určuje které týdny mají data (žádná iterace přes týdny).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.raw_report_brand`
(
  owning_brand_id  STRING,     -- brand jehož monitoring volání provedlo
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


-- ------------------------------------------------------------
-- raw_report_topic_brand
-- Zdroj: POST /v1/metrics/report s filters.topicId per každý topic
-- Jeden řádek per brand (vlastní i competitor) per topic per snapshot_date per owning_brand per ETL run.
-- Nahrazuje raw_report_topic — obsahuje i competitors, nejen vlastní brand.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.raw_report_topic_brand`
(
  owning_brand_id  STRING,     -- brand jehož monitoring volání provedlo
  topic_id         STRING,
  topic_name       STRING,
  snapshot_date    TIMESTAMP,  -- timestamp snapshotu z API
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


-- ------------------------------------------------------------
-- raw_citations
-- Zdroj: POST /v1/metrics/citations → domainSummary.topDomainsByQuery
-- Jeden řádek per URL × engine × query per brand per ETL run.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `libor-matejkacz.RankScaleDashboard.raw_citations`
(
  brand_id       STRING,
  search_term_id STRING,
  query          STRING,
  engine         STRING,
  domain         STRING,
  url            STRING,
  occurrences    INT64,
  etl_loaded_at  TIMESTAMP
);
