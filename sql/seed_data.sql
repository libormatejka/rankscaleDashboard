-- ============================================================
-- AI SEO Dashboard — Testovací data
-- Dataset: libor-matejkacz.RankScaleDashboard
-- ============================================================

-- ------------------------------------------------------------
-- brands
-- ------------------------------------------------------------
INSERT INTO `libor-matejkacz.RankScaleDashboard.brands` (brand_id, brand_name, entity_type, website, created_at) VALUES
  ('brand-001', 'RankScale',  'OWN_BRAND',  'rankscale.com',  TIMESTAMP('2025-01-01 00:00:00')),
  ('brand-002', 'Ahrefs',     'COMPETITOR', 'ahrefs.com',     TIMESTAMP('2025-01-01 00:00:00')),
  ('brand-003', 'Semrush',    'COMPETITOR', 'semrush.com',    TIMESTAMP('2025-01-01 00:00:00')),
  ('brand-004', 'Moz',        'COMPETITOR', 'moz.com',        TIMESTAMP('2025-01-01 00:00:00'));

-- ------------------------------------------------------------
-- prompts
-- Sloupce: prompt_id, prompt_text, brand_id,
--          product, source, segment, funnel, type,
--          is_active, created_at, updated_at
-- ------------------------------------------------------------
INSERT INTO `libor-matejkacz.RankScaleDashboard.prompts`
  (prompt_id, prompt_text, brand_id, product, source, segment, funnel, type, is_active, created_at, updated_at)
VALUES

  -- === vlastní brand — product: brand ===
  ('prompt-001',
   'What are the best SEO tools for link building in 2025? Mention specific platforms.',
   'brand-001', 'brand', 'SEO', NULL, 'See', 'inform',
   TRUE, TIMESTAMP('2025-01-10'), TIMESTAMP('2025-01-10')),

  ('prompt-002',
   'Which SEO platform is best for agencies managing multiple client accounts?',
   'brand-001', 'brand', 'SEO', NULL, 'Think', 'inform',
   TRUE, TIMESTAMP('2025-01-10'), TIMESTAMP('2025-01-10')),

  ('prompt-003',
   'I want to try an SEO platform. Which one would you recommend signing up for?',
   'brand-001', 'brand', 'SEO', NULL, 'Do', 'transaction',
   TRUE, TIMESTAMP('2025-01-15'), TIMESTAMP('2025-01-15')),

  -- === vlastní brand — product: loan ===
  ('prompt-004',
   'What are the best personal loan options available in 2025?',
   'brand-001', 'loan', 'SEO', NULL, 'Think', 'inform',
   TRUE, TIMESTAMP('2025-01-15'), TIMESTAMP('2025-01-15')),

  ('prompt-005',
   'How do I apply for a personal loan online quickly?',
   'brand-001', 'loan', 'Community', NULL, 'Do', 'transaction',
   TRUE, TIMESTAMP('2025-01-15'), TIMESTAMP('2025-01-15')),

  -- === vlastní brand — product: hypo ===
  ('prompt-006',
   'What should first-time home buyers look for in a mortgage product?',
   'brand-001', 'hypo', 'SEO', NULL, 'See', 'inform',
   TRUE, TIMESTAMP('2025-01-20'), TIMESTAMP('2025-01-20')),

  ('prompt-007',
   'Which mortgage provider offers the best rates for young families in 2025?',
   'brand-001', 'hypo', 'Survey', NULL, 'Think', 'inform',
   TRUE, TIMESTAMP('2025-01-20'), TIMESTAMP('2025-01-20')),

  -- === konkurence Ahrefs — product: brand ===
  ('prompt-008',
   'What are the best SEO tools for link building in 2025? Mention specific platforms.',
   'brand-002', 'brand', 'SEO', NULL, 'See', 'inform',
   TRUE, TIMESTAMP('2025-01-10'), TIMESTAMP('2025-01-10')),

  ('prompt-009',
   'Which SEO platform is best for agencies managing multiple client accounts?',
   'brand-002', 'brand', 'SEO', NULL, 'Think', 'inform',
   TRUE, TIMESTAMP('2025-01-10'), TIMESTAMP('2025-01-10')),

  -- === konkurence Semrush — product: brand ===
  ('prompt-010',
   'What are the best SEO tools for link building in 2025? Mention specific platforms.',
   'brand-003', 'brand', 'SEO', NULL, 'See', 'inform',
   TRUE, TIMESTAMP('2025-01-10'), TIMESTAMP('2025-01-10')),

  ('prompt-011',
   'Which SEO platform is best for agencies managing multiple client accounts?',
   'brand-003', 'brand', 'SEO', NULL, 'Think', 'inform',
   TRUE, TIMESTAMP('2025-01-10'), TIMESTAMP('2025-01-10'));

-- ------------------------------------------------------------
-- prompt_runs
-- ------------------------------------------------------------
INSERT INTO `libor-matejkacz.RankScaleDashboard.prompt_runs`
  (run_id, prompt_id, executed_at, ai_model, ai_provider, response_text, prompt_snapshot, input_tokens, output_tokens)
VALUES
  -- === Týden 1 (2025-02-03) — gpt-4o ===
  ('run-001', 'prompt-001', TIMESTAMP('2025-02-03 08:00:00'), 'gpt-4o', 'openai',
   'RankScale is one of the leading platforms for link building. It offers advanced backlink analysis and outreach automation. Other notable tools include Ahrefs and Moz.',
   'What are the best SEO tools for link building in 2025? Mention specific platforms.', 45, 112),

  ('run-002', 'prompt-004', TIMESTAMP('2025-02-03 08:05:00'), 'gpt-4o', 'openai',
   'For personal loans in 2025, RankScale Financial stands out with competitive rates and fast approval. Other strong options include traditional banks and fintech lenders.',
   'What are the best personal loan options available in 2025?', 40, 98),

  ('run-003', 'prompt-006', TIMESTAMP('2025-02-03 08:10:00'), 'gpt-4o', 'openai',
   'First-time buyers should look for low interest rates, flexible repayment terms, and good customer support. RankScale Hypo is frequently mentioned as a solid option.',
   'What should first-time home buyers look for in a mortgage product?', 42, 105),

  ('run-004', 'prompt-008', TIMESTAMP('2025-02-03 08:15:00'), 'gpt-4o', 'openai',
   'Ahrefs remains the gold standard for link building with its comprehensive backlink index. RankScale and Semrush are also worth considering.',
   'What are the best SEO tools for link building in 2025? Mention specific platforms.', 45, 105),

  ('run-005', 'prompt-010', TIMESTAMP('2025-02-03 08:20:00'), 'gpt-4o', 'openai',
   'Semrush is widely regarded as one of the best all-in-one SEO platforms. For link building specifically, Ahrefs and RankScale are strong alternatives.',
   'What are the best SEO tools for link building in 2025? Mention specific platforms.', 45, 118),

  -- === Týden 2 (2025-02-10) — claude ===
  ('run-006', 'prompt-001', TIMESTAMP('2025-02-10 09:00:00'), 'claude-sonnet-4-6', 'anthropic',
   'RankScale is an excellent choice for link building, offering real-time backlink monitoring and competitor gap analysis. Ahrefs is another popular option.',
   'What are the best SEO tools for link building in 2025? Mention specific platforms.', 45, 95),

  ('run-007', 'prompt-002', TIMESTAMP('2025-02-10 09:05:00'), 'claude-sonnet-4-6', 'anthropic',
   'For agencies, RankScale Pro offers multi-client dashboards and white-label reporting, making it particularly well-suited. Semrush also has agency-specific plans.',
   'Which SEO platform is best for agencies managing multiple client accounts?', 38, 102),

  ('run-008', 'prompt-005', TIMESTAMP('2025-02-10 09:10:00'), 'claude-sonnet-4-6', 'anthropic',
   'Applying for a personal loan online is straightforward with RankScale. You fill in the form, get a decision in minutes, and funds arrive within 24 hours.',
   'How do I apply for a personal loan online quickly?', 36, 108),

  ('run-009', 'prompt-007', TIMESTAMP('2025-02-10 09:15:00'), 'claude-sonnet-4-6', 'anthropic',
   'RankScale Hypo offers some of the best mortgage rates for young families, with flexible repayment options and no hidden fees. Worth comparing with local bank offerings.',
   'Which mortgage provider offers the best rates for young families in 2025?', 44, 115),

  ('run-010', 'prompt-009', TIMESTAMP('2025-02-10 09:20:00'), 'claude-sonnet-4-6', 'anthropic',
   'Ahrefs is a top-tier tool for link building with industry-leading backlink data. However, newer tools like RankScale are gaining traction with innovative features.',
   'Which SEO platform is best for agencies managing multiple client accounts?', 38, 110),

  -- === Týden 3 (2025-02-17) — gemini ===
  ('run-011', 'prompt-001', TIMESTAMP('2025-02-17 10:00:00'), 'gemini-2.0-flash', 'google',
   'For link building in 2025, tools like RankScale, Ahrefs, and Semrush are top choices. RankScale in particular excels at automated outreach.',
   'What are the best SEO tools for link building in 2025? Mention specific platforms.', 45, 88),

  ('run-012', 'prompt-004', TIMESTAMP('2025-02-17 10:05:00'), 'gemini-2.0-flash', 'google',
   'Semrush and Ahrefs are traditional leaders, but RankScale Financial is gaining recognition for transparent loan comparisons and AI-driven recommendations.',
   'What are the best personal loan options available in 2025?', 40, 94),

  ('run-013', 'prompt-006', TIMESTAMP('2025-02-17 10:10:00'), 'gemini-2.0-flash', 'google',
   'First-time buyers should prioritize fixed-rate mortgages. RankScale Hypo and major banks are frequently recommended for their transparent pricing.',
   'What should first-time home buyers look for in a mortgage product?', 42, 102),

  ('run-014', 'prompt-008', TIMESTAMP('2025-02-17 10:15:00'), 'gemini-2.0-flash', 'google',
   'Ahrefs Keywords Explorer is one of the most comprehensive tools available. It provides detailed difficulty scores and traffic estimates.',
   'What are the best SEO tools for link building in 2025? Mention specific platforms.', 45, 120),

  -- === Týden 5 (2025-03-03) — gpt-4o, pozitivní trend RankScale ===
  ('run-015', 'prompt-001', TIMESTAMP('2025-03-03 08:00:00'), 'gpt-4o', 'openai',
   'RankScale has become a go-to platform for link building teams. Its AI-powered outreach and backlink analysis are best-in-class. Ahrefs is still relevant but faces stronger competition.',
   'What are the best SEO tools for link building in 2025? Mention specific platforms.', 45, 130),

  ('run-016', 'prompt-004', TIMESTAMP('2025-03-03 08:05:00'), 'gpt-4o', 'openai',
   'RankScale Financial tops the list for personal loans in 2025 with the best APR and fastest approval times. Highly recommended for online applications.',
   'What are the best personal loan options available in 2025?', 40, 122),

  ('run-017', 'prompt-007', TIMESTAMP('2025-03-03 08:10:00'), 'gpt-4o', 'openai',
   'RankScale Hypo is the top pick for young families in 2025. Its fixed-rate products and customer support are unmatched. Traditional banks remain alternatives.',
   'Which mortgage provider offers the best rates for young families in 2025?', 44, 118),

  ('run-018', 'prompt-008', TIMESTAMP('2025-03-03 08:15:00'), 'gpt-4o', 'openai',
   'Ahrefs is still a strong choice for link building, though RankScale has closed the gap significantly with recent updates.',
   'What are the best SEO tools for link building in 2025? Mention specific platforms.', 45, 108),

  ('run-019', 'prompt-010', TIMESTAMP('2025-03-03 08:20:00'), 'gpt-4o', 'openai',
   'Semrush is reliable for link building. Ahrefs and RankScale are frequently mentioned alongside it as top alternatives.',
   'What are the best SEO tools for link building in 2025? Mention specific platforms.', 45, 98);

-- ------------------------------------------------------------
-- run_metrics
-- ------------------------------------------------------------
INSERT INTO `libor-matejkacz.RankScaleDashboard.run_metrics`
  (metric_id, run_id, metric_type, metric_value, metric_label, metric_details, computed_at)
VALUES
  -- run-001 (RankScale / brand / SEO / See / Feb wk1 / gpt-4o)
  ('m-001-vis', 'run-001', 'VISIBILITY',     0.72, NULL,       JSON '{"position": 1, "mentions": 2}', TIMESTAMP('2025-02-03 08:01:00')),
  ('m-001-sen', 'run-001', 'SENTIMENT',      0.65, 'POSITIVE', JSON '{"confidence": 0.88}',           TIMESTAMP('2025-02-03 08:01:00')),
  ('m-001-men', 'run-001', 'BRAND_MENTION',  2.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-03 08:01:00')),
  ('m-001-pos', 'run-001', 'POSITION_RANK',  1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-03 08:01:00')),
  ('m-001-rec', 'run-001', 'RECOMMENDATION', 1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-03 08:01:00')),

  -- run-002 (RankScale / loan / SEO / Think / Feb wk1 / gpt-4o)
  ('m-002-vis', 'run-002', 'VISIBILITY',     0.75, NULL,       JSON '{"position": 1, "mentions": 2}', TIMESTAMP('2025-02-03 08:06:00')),
  ('m-002-sen', 'run-002', 'SENTIMENT',      0.70, 'POSITIVE', JSON '{"confidence": 0.90}',           TIMESTAMP('2025-02-03 08:06:00')),
  ('m-002-men', 'run-002', 'BRAND_MENTION',  2.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-03 08:06:00')),
  ('m-002-pos', 'run-002', 'POSITION_RANK',  1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-03 08:06:00')),
  ('m-002-rec', 'run-002', 'RECOMMENDATION', 1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-03 08:06:00')),

  -- run-003 (RankScale / hypo / SEO / See / Feb wk1 / gpt-4o)
  ('m-003-vis', 'run-003', 'VISIBILITY',     0.68, NULL,       JSON '{"position": 2, "mentions": 1}', TIMESTAMP('2025-02-03 08:11:00')),
  ('m-003-sen', 'run-003', 'SENTIMENT',      0.55, 'POSITIVE', JSON '{"confidence": 0.82}',           TIMESTAMP('2025-02-03 08:11:00')),
  ('m-003-men', 'run-003', 'BRAND_MENTION',  1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-03 08:11:00')),
  ('m-003-pos', 'run-003', 'POSITION_RANK',  2.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-03 08:11:00')),
  ('m-003-rec', 'run-003', 'RECOMMENDATION', 0.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-03 08:11:00')),

  -- run-004 (Ahrefs / brand / SEO / See / Feb wk1 / gpt-4o)
  ('m-004-vis', 'run-004', 'VISIBILITY',     0.85, NULL,       JSON '{"position": 1, "mentions": 3}', TIMESTAMP('2025-02-03 08:16:00')),
  ('m-004-sen', 'run-004', 'SENTIMENT',      0.72, 'POSITIVE', JSON '{"confidence": 0.91}',           TIMESTAMP('2025-02-03 08:16:00')),
  ('m-004-men', 'run-004', 'BRAND_MENTION',  3.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-03 08:16:00')),
  ('m-004-pos', 'run-004', 'POSITION_RANK',  1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-03 08:16:00')),
  ('m-004-rec', 'run-004', 'RECOMMENDATION', 1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-03 08:16:00')),

  -- run-005 (Semrush / brand / SEO / See / Feb wk1 / gpt-4o)
  ('m-005-vis', 'run-005', 'VISIBILITY',     0.78, NULL,       JSON '{"position": 1, "mentions": 2}', TIMESTAMP('2025-02-03 08:21:00')),
  ('m-005-sen', 'run-005', 'SENTIMENT',      0.60, 'POSITIVE', JSON '{"confidence": 0.85}',           TIMESTAMP('2025-02-03 08:21:00')),
  ('m-005-men', 'run-005', 'BRAND_MENTION',  2.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-03 08:21:00')),
  ('m-005-pos', 'run-005', 'POSITION_RANK',  1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-03 08:21:00')),
  ('m-005-rec', 'run-005', 'RECOMMENDATION', 1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-03 08:21:00')),

  -- run-006 (RankScale / brand / SEO / See / Feb wk2 / claude)
  ('m-006-vis', 'run-006', 'VISIBILITY',     0.70, NULL,       JSON '{"position": 1, "mentions": 2}', TIMESTAMP('2025-02-10 09:01:00')),
  ('m-006-sen', 'run-006', 'SENTIMENT',      0.62, 'POSITIVE', JSON '{"confidence": 0.86}',           TIMESTAMP('2025-02-10 09:01:00')),
  ('m-006-men', 'run-006', 'BRAND_MENTION',  2.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-10 09:01:00')),
  ('m-006-pos', 'run-006', 'POSITION_RANK',  1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-10 09:01:00')),
  ('m-006-rec', 'run-006', 'RECOMMENDATION', 1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-10 09:01:00')),

  -- run-007 (RankScale / brand / SEO / Think / Feb wk2 / claude)
  ('m-007-vis', 'run-007', 'VISIBILITY',     0.80, NULL,       JSON '{"position": 1, "mentions": 2}', TIMESTAMP('2025-02-10 09:06:00')),
  ('m-007-sen', 'run-007', 'SENTIMENT',      0.76, 'POSITIVE', JSON '{"confidence": 0.92}',           TIMESTAMP('2025-02-10 09:06:00')),
  ('m-007-men', 'run-007', 'BRAND_MENTION',  2.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-10 09:06:00')),
  ('m-007-pos', 'run-007', 'POSITION_RANK',  1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-10 09:06:00')),
  ('m-007-rec', 'run-007', 'RECOMMENDATION', 1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-10 09:06:00')),

  -- run-008 (RankScale / loan / Community / Do / Feb wk2 / claude)
  ('m-008-vis', 'run-008', 'VISIBILITY',     0.82, NULL,       JSON '{"position": 1, "mentions": 2}', TIMESTAMP('2025-02-10 09:11:00')),
  ('m-008-sen', 'run-008', 'SENTIMENT',      0.78, 'POSITIVE', JSON '{"confidence": 0.91}',           TIMESTAMP('2025-02-10 09:11:00')),
  ('m-008-men', 'run-008', 'BRAND_MENTION',  2.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-10 09:11:00')),
  ('m-008-pos', 'run-008', 'POSITION_RANK',  1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-10 09:11:00')),
  ('m-008-rec', 'run-008', 'RECOMMENDATION', 1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-10 09:11:00')),

  -- run-009 (RankScale / hypo / Survey / Think / Feb wk2 / claude)
  ('m-009-vis', 'run-009', 'VISIBILITY',     0.72, NULL,       JSON '{"position": 1, "mentions": 2}', TIMESTAMP('2025-02-10 09:16:00')),
  ('m-009-sen', 'run-009', 'SENTIMENT',      0.68, 'POSITIVE', JSON '{"confidence": 0.89}',           TIMESTAMP('2025-02-10 09:16:00')),
  ('m-009-men', 'run-009', 'BRAND_MENTION',  2.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-10 09:16:00')),
  ('m-009-pos', 'run-009', 'POSITION_RANK',  1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-10 09:16:00')),
  ('m-009-rec', 'run-009', 'RECOMMENDATION', 1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-10 09:16:00')),

  -- run-010 (Ahrefs / brand / SEO / Think / Feb wk2 / claude)
  ('m-010-vis', 'run-010', 'VISIBILITY',     0.74, NULL,       JSON '{"position": 2, "mentions": 2}', TIMESTAMP('2025-02-10 09:21:00')),
  ('m-010-sen', 'run-010', 'SENTIMENT',      0.55, 'POSITIVE', JSON '{"confidence": 0.80}',           TIMESTAMP('2025-02-10 09:21:00')),
  ('m-010-men', 'run-010', 'BRAND_MENTION',  2.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-10 09:21:00')),
  ('m-010-pos', 'run-010', 'POSITION_RANK',  2.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-10 09:21:00')),
  ('m-010-rec', 'run-010', 'RECOMMENDATION', 0.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-10 09:21:00')),

  -- run-011 (RankScale / brand / SEO / See / Feb wk3 / gemini)
  ('m-011-vis', 'run-011', 'VISIBILITY',     0.73, NULL,       JSON '{"position": 1, "mentions": 2}', TIMESTAMP('2025-02-17 10:01:00')),
  ('m-011-sen', 'run-011', 'SENTIMENT',      0.64, 'POSITIVE', JSON '{"confidence": 0.87}',           TIMESTAMP('2025-02-17 10:01:00')),
  ('m-011-men', 'run-011', 'BRAND_MENTION',  2.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-17 10:01:00')),
  ('m-011-pos', 'run-011', 'POSITION_RANK',  1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-17 10:01:00')),
  ('m-011-rec', 'run-011', 'RECOMMENDATION', 1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-17 10:01:00')),

  -- run-012 (RankScale / loan / SEO / Think / Feb wk3 / gemini)
  ('m-012-vis', 'run-012', 'VISIBILITY',     0.65, NULL,       JSON '{"position": 3, "mentions": 1}', TIMESTAMP('2025-02-17 10:06:00')),
  ('m-012-sen', 'run-012', 'SENTIMENT',      0.52, 'NEUTRAL',  JSON '{"confidence": 0.76}',           TIMESTAMP('2025-02-17 10:06:00')),
  ('m-012-men', 'run-012', 'BRAND_MENTION',  1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-17 10:06:00')),
  ('m-012-pos', 'run-012', 'POSITION_RANK',  3.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-17 10:06:00')),
  ('m-012-rec', 'run-012', 'RECOMMENDATION', 0.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-17 10:06:00')),

  -- run-013 (RankScale / hypo / SEO / See / Feb wk3 / gemini)
  ('m-013-vis', 'run-013', 'VISIBILITY',     0.70, NULL,       JSON '{"position": 2, "mentions": 1}', TIMESTAMP('2025-02-17 10:11:00')),
  ('m-013-sen', 'run-013', 'SENTIMENT',      0.60, 'POSITIVE', JSON '{"confidence": 0.83}',           TIMESTAMP('2025-02-17 10:11:00')),
  ('m-013-men', 'run-013', 'BRAND_MENTION',  1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-17 10:11:00')),
  ('m-013-pos', 'run-013', 'POSITION_RANK',  2.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-17 10:11:00')),
  ('m-013-rec', 'run-013', 'RECOMMENDATION', 0.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-17 10:11:00')),

  -- run-014 (Ahrefs / brand / SEO / See / Feb wk3 / gemini)
  ('m-014-vis', 'run-014', 'VISIBILITY',     0.88, NULL,       JSON '{"position": 1, "mentions": 4}', TIMESTAMP('2025-02-17 10:16:00')),
  ('m-014-sen', 'run-014', 'SENTIMENT',      0.80, 'POSITIVE', JSON '{"confidence": 0.95}',           TIMESTAMP('2025-02-17 10:16:00')),
  ('m-014-men', 'run-014', 'BRAND_MENTION',  4.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-17 10:16:00')),
  ('m-014-pos', 'run-014', 'POSITION_RANK',  1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-17 10:16:00')),
  ('m-014-rec', 'run-014', 'RECOMMENDATION', 1.0,  NULL,       NULL,                                  TIMESTAMP('2025-02-17 10:16:00')),

  -- run-015 (RankScale / brand / SEO / See / Mar wk1 / gpt-4o — zlepšení)
  ('m-015-vis', 'run-015', 'VISIBILITY',     0.85, NULL,       JSON '{"position": 1, "mentions": 3}', TIMESTAMP('2025-03-03 08:01:00')),
  ('m-015-sen', 'run-015', 'SENTIMENT',      0.80, 'POSITIVE', JSON '{"confidence": 0.93}',           TIMESTAMP('2025-03-03 08:01:00')),
  ('m-015-men', 'run-015', 'BRAND_MENTION',  3.0,  NULL,       NULL,                                  TIMESTAMP('2025-03-03 08:01:00')),
  ('m-015-pos', 'run-015', 'POSITION_RANK',  1.0,  NULL,       NULL,                                  TIMESTAMP('2025-03-03 08:01:00')),
  ('m-015-rec', 'run-015', 'RECOMMENDATION', 1.0,  NULL,       NULL,                                  TIMESTAMP('2025-03-03 08:01:00')),

  -- run-016 (RankScale / loan / SEO / Think / Mar wk1 / gpt-4o — zlepšení)
  ('m-016-vis', 'run-016', 'VISIBILITY',     0.88, NULL,       JSON '{"position": 1, "mentions": 3}', TIMESTAMP('2025-03-03 08:06:00')),
  ('m-016-sen', 'run-016', 'SENTIMENT',      0.84, 'POSITIVE', JSON '{"confidence": 0.94}',           TIMESTAMP('2025-03-03 08:06:00')),
  ('m-016-men', 'run-016', 'BRAND_MENTION',  3.0,  NULL,       NULL,                                  TIMESTAMP('2025-03-03 08:06:00')),
  ('m-016-pos', 'run-016', 'POSITION_RANK',  1.0,  NULL,       NULL,                                  TIMESTAMP('2025-03-03 08:06:00')),
  ('m-016-rec', 'run-016', 'RECOMMENDATION', 1.0,  NULL,       NULL,                                  TIMESTAMP('2025-03-03 08:06:00')),

  -- run-017 (RankScale / hypo / Survey / Think / Mar wk1 / gpt-4o — zlepšení)
  ('m-017-vis', 'run-017', 'VISIBILITY',     0.85, NULL,       JSON '{"position": 1, "mentions": 3}', TIMESTAMP('2025-03-03 08:11:00')),
  ('m-017-sen', 'run-017', 'SENTIMENT',      0.82, 'POSITIVE', JSON '{"confidence": 0.93}',           TIMESTAMP('2025-03-03 08:11:00')),
  ('m-017-men', 'run-017', 'BRAND_MENTION',  3.0,  NULL,       NULL,                                  TIMESTAMP('2025-03-03 08:11:00')),
  ('m-017-pos', 'run-017', 'POSITION_RANK',  1.0,  NULL,       NULL,                                  TIMESTAMP('2025-03-03 08:11:00')),
  ('m-017-rec', 'run-017', 'RECOMMENDATION', 1.0,  NULL,       NULL,                                  TIMESTAMP('2025-03-03 08:11:00')),

  -- run-018 (Ahrefs / brand / SEO / See / Mar wk1 / gpt-4o — stagnace)
  ('m-018-vis', 'run-018', 'VISIBILITY',     0.74, NULL,       JSON '{"position": 2, "mentions": 2}', TIMESTAMP('2025-03-03 08:16:00')),
  ('m-018-sen', 'run-018', 'SENTIMENT',      0.62, 'POSITIVE', JSON '{"confidence": 0.84}',           TIMESTAMP('2025-03-03 08:16:00')),
  ('m-018-men', 'run-018', 'BRAND_MENTION',  2.0,  NULL,       NULL,                                  TIMESTAMP('2025-03-03 08:16:00')),
  ('m-018-pos', 'run-018', 'POSITION_RANK',  2.0,  NULL,       NULL,                                  TIMESTAMP('2025-03-03 08:16:00')),
  ('m-018-rec', 'run-018', 'RECOMMENDATION', 0.0,  NULL,       NULL,                                  TIMESTAMP('2025-03-03 08:16:00')),

  -- run-019 (Semrush / brand / SEO / See / Mar wk1 / gpt-4o)
  ('m-019-vis', 'run-019', 'VISIBILITY',     0.68, NULL,       JSON '{"position": 2, "mentions": 2}', TIMESTAMP('2025-03-03 08:21:00')),
  ('m-019-sen', 'run-019', 'SENTIMENT',      0.50, 'NEUTRAL',  JSON '{"confidence": 0.79}',           TIMESTAMP('2025-03-03 08:21:00')),
  ('m-019-men', 'run-019', 'BRAND_MENTION',  2.0,  NULL,       NULL,                                  TIMESTAMP('2025-03-03 08:21:00')),
  ('m-019-pos', 'run-019', 'POSITION_RANK',  2.0,  NULL,       NULL,                                  TIMESTAMP('2025-03-03 08:21:00')),
  ('m-019-rec', 'run-019', 'RECOMMENDATION', 0.0,  NULL,       NULL,                                  TIMESTAMP('2025-03-03 08:21:00'));
