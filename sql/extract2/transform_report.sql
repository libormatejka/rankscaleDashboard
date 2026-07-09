-- ============================================================
-- Extract 2 — transformace z raw_report_ vrstvy
-- Projekt:  libor-matejkacz
-- Dataset:  RankScaleDashboard
-- ============================================================
-- Spouštět manuálně po dokončení report extractu.
-- Předpoklad: tabulky existují (viz schema_report.sql).
-- Pořadí: L1 → L2_brand → L2_tags (každý krok závisí na předchozím)
-- ============================================================


-- ── 1. L1_report_topic_brand ─────────────────────────────────────────────────
-- Deduplikace raw dat — při vícenásobném spuštění extractu ve stejný den
-- zůstane vždy jen nejnovější záznam per grain.

TRUNCATE TABLE `libor-matejkacz.RankScaleDashboard.L1_report_topic_brand`;

INSERT INTO `libor-matejkacz.RankScaleDashboard.L1_report_topic_brand`
SELECT * EXCEPT (rn)
FROM (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY owning_brand_id, topic_id, brand_name, snapshot_date
      ORDER BY etl_loaded_at DESC
    ) AS rn
  FROM `libor-matejkacz.RankScaleDashboard.raw_report_topic_brand`
)
WHERE rn = 1;


-- ── 2. L2_report_topic_brand ─────────────────────────────────────────────────
-- Flat tabulka pro BI — přidává snapshot_week, převádí snapshot_date na DATE.

TRUNCATE TABLE `libor-matejkacz.RankScaleDashboard.L2_report_topic_brand`;

INSERT INTO `libor-matejkacz.RankScaleDashboard.L2_report_topic_brand`
SELECT
  owning_brand_id,
  topic_id,
  topic_name,
  tags,
  DATE(snapshot_date)                        AS snapshot_date,
  FORMAT_DATE('%G-%V', DATE(snapshot_date))  AS snapshot_week,
  brand_name,
  is_own_brand,
  visibility_score,
  sentiment,
  avg_position,
  detection_rate,
  top3,
  mentions,
  citations,
  etl_loaded_at
FROM `libor-matejkacz.RankScaleDashboard.L1_report_topic_brand`;


-- ── 3. L2_report_topic_tags ──────────────────────────────────────────────────
-- Bridge tabulka — unnested tagy, 1 řádek per topic × tag.
-- Použij pro filtrování L2_report_topic_brand podle tagu:
--   JOIN L2_report_topic_tags t ON t.topic_id        = r.topic_id
--                               AND t.owning_brand_id = r.owning_brand_id
--   WHERE t.tag = 'product-brand'

TRUNCATE TABLE `libor-matejkacz.RankScaleDashboard.L2_report_topic_tags`;

INSERT INTO `libor-matejkacz.RankScaleDashboard.L2_report_topic_tags`
SELECT DISTINCT
  owning_brand_id,
  topic_id,
  topic_name,
  TRIM(tag) AS tag
FROM `libor-matejkacz.RankScaleDashboard.L2_report_topic_brand`,
  UNNEST(JSON_VALUE_ARRAY(tags)) AS tag
WHERE tags IS NOT NULL
  AND tags NOT IN ('[]', 'null', '');
