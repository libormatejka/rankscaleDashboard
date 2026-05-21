-- ============================================================
-- Oprava chybějících sloupců v dim_brands
-- Spusť každý příkaz zvlášť v BigQuery Console.
-- ALTER TABLE ADD COLUMN IF NOT EXISTS je bezpečný – pokud
-- sloupec existuje, nic se nestane.
-- ============================================================

ALTER TABLE `libor-matejkacz.RankScaleDashboard.dim_brands`
  ADD COLUMN IF NOT EXISTS is_own_brand      BOOL,
  ADD COLUMN IF NOT EXISTS search_term_count INT64;
