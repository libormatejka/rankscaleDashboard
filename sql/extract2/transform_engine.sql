-- ============================================================
-- Extract 2 — transformace engine dat z L0_report_engine
-- Projekt:  libor-matejkacz
-- Dataset:  RankScaleDashboard
-- ============================================================
-- Spouštět manuálně po dokončení report extractu.
-- Předpoklad: tabulky existují (viz schema_engine.sql).
-- Pořadí: L1 → L2 (každý krok závisí na předchozím)
-- ============================================================


-- ── 1. L1_report_engine ──────────────────────────────────────────────────────
-- Deduplikace L0 dat — při vícenásobném spuštění extractu ve stejný den
-- zůstane vždy jen nejnovější záznam per grain.

TRUNCATE TABLE `libor-matejkacz.RankScaleDashboard.L1_report_engine`;

INSERT INTO `libor-matejkacz.RankScaleDashboard.L1_report_engine`
SELECT * EXCEPT (rn)
FROM (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY owning_brand_id, topic_id, engine_id, brand_name, snapshot_date
      ORDER BY etl_loaded_at DESC
    ) AS rn
  FROM `libor-matejkacz.RankScaleDashboard.L0_report_engine`
)
WHERE rn = 1;


-- ── 2. L2_report_engine ──────────────────────────────────────────────────────
-- Flat tabulka pro BI — přidává snapshot_week, převádí snapshot_date na DATE.

TRUNCATE TABLE `libor-matejkacz.RankScaleDashboard.L2_report_engine`;

INSERT INTO `libor-matejkacz.RankScaleDashboard.L2_report_engine`
SELECT
  owning_brand_id,
  topic_id,
  topic_name,
  engine_id,
  DATE(snapshot_date)                        AS snapshot_date,
  FORMAT_DATE('%G-%V', DATE(snapshot_date))  AS snapshot_week,
  brand_name,
  visibility_score,
  sentiment,
  avg_position,
  detection_rate,
  top3,
  mentions,
  citations,
  etl_loaded_at
FROM `libor-matejkacz.RankScaleDashboard.L1_report_engine`;
