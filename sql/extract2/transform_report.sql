-- ============================================================
-- Extract 2 — transformace z L0_report_table do L1_report_table
-- Projekt:  libor-matejkacz
-- Dataset:  RankScaleDashboard
-- ============================================================
-- Spouštět po každém ETL runu (Extract 2).
-- Předpoklad: obě tabulky existují (viz schema_report.sql).
-- ============================================================


-- ── L1_report_table ──────────────────────────────────────────────────────────
-- Deduplikace L0 dat přes business_key — při vícenásobném spuštění extractu
-- zůstane vždy jen nejnovější záznam per grain.

TRUNCATE TABLE `libor-matejkacz.RankScaleDashboard.L1_report_table`;

INSERT INTO `libor-matejkacz.RankScaleDashboard.L1_report_table`
SELECT * EXCEPT (rn)
FROM (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY business_key
      ORDER BY etl_loaded_at DESC
    ) AS rn
  FROM `libor-matejkacz.RankScaleDashboard.L0_report_table`
)
WHERE rn = 1;
