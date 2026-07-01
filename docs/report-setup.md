# Report Setup — Looker Studio & Tableau

Návod na napojení L2 vrstvy z BigQuery do BI nástrojů.

**Předpoklad:** L2 tabulky jsou naplněné (spuštěn `transform_l2.sql`).
**BigQuery dataset:** `libor-matejkacz.RankScaleDashboard`

---

## Looker Studio (Google Data Studio)

### 1. Vytvoř nový report

1. Jdi na [lookerstudio.google.com](https://lookerstudio.google.com)
2. Klikni **Create → Report**

### 2. Přidej datový zdroj — L2_snapshots

1. V dialogu **Add data to report** vyber **BigQuery**
2. Přihlaš se Google účtem (stejným, pod kterým běží GCP projekt `libor-matejkacz`)
3. Vyber:
   - **Project:** `libor-matejkacz`
   - **Dataset:** `RankScaleDashboard`
   - **Table:** `L2_snapshots`
4. Klikni **Add → Add to report**

### 3. Přidej zbývající datové zdroje

Stejným postupem přidej další tabulky jako samostatné zdroje:

| Zdroj | Tabulka | K čemu |
|---|---|---|
| L2_snapshots | `L2_snapshots` | Hlavní metriky |
| L2_search_term_tags | `L2_search_term_tags` | Filtr podle tagu |
| L2_citations | `L2_citations` | Citované domény |
| L2_answer_texts | `L2_answer_texts` | Texty AI odpovědí |

### 4. Nastav blended data pro tag filtr

Protože tagy jsou v samostatné tabulce, potřebuješ blend:

1. V reportu klikni **Resource → Manage blended data → Add a blend**
2. **Left table:** `L2_snapshots` — join key: `search_term_id`
3. **Right table:** `L2_search_term_tags` — join key: `search_term_id`
4. Join type: **Left outer**
5. Z blended zdroje přidej dimenzi `tag` do filtrů

### 5. Doporučené typy grafů

| Pohled | Typ grafu | Dimenze | Metrika |
|---|---|---|---|
| Vývoj visibility v čase | Time series | `snapshot_week` | `AVG(visibility_score)` |
| Brand vs. konkurence | Bar chart | `brand_name` | `visibility_score` |
| Metriky per topic | Scorecard / Bar | `topic_name` | `AVG(visibility_score)` |
| AI Share of Voice | Pie / Donut | `brand_name` | `AVG(ai_share_of_voice)` |
| Top citované domény | Bar chart | `domain` | `SUM(occurrences)` |

### 6. Doporučené filtry (Add a control)

- **topic_name** — Drop-down list
- **engine** — Drop-down list
- **is_own_brand** — Drop-down list (TRUE/FALSE)
- **snapshot_week** — Date range nebo Drop-down
- **tag** — Drop-down (z blended zdroje `L2_search_term_tags`)

---

## Tableau

### 1. Připoj se k BigQuery

1. Otevři Tableau Desktop
2. Na úvodní obrazovce vlevo vyber **Google BigQuery**
3. Přihlašování:
   - **OAuth (doporučeno):** klikni Sign In → přihlásíš se Google účtem
   - **Service Account:** vyber soubor JSON service account klíče (stejný jako `GCP_SA_JSON` v GitHub Secrets)
4. Vyber:
   - **Billing Project:** `libor-matejkacz`
   - **Project:** `libor-matejkacz`
   - **Dataset:** `RankScaleDashboard`

### 2. Přidej tabulky

1. Z levého panelu přetáhni `L2_snapshots` na plátno — to bude tvůj hlavní zdroj
2. Přidej `L2_search_term_tags`:
   - Přetáhni ji vedle `L2_snapshots`
   - Tableau navrhne join — nastav: `L2_snapshots.search_term_id = L2_search_term_tags.search_term_id`
   - Join type: **Left**

### 3. Ostatní tabulky jako samostatné Data Sources

`L2_citations` a `L2_answer_texts` přidej jako **nové Data Sources** (ne join):

1. Klikni **Data → New Data Source**
2. Znovu BigQuery, stejný projekt/dataset
3. Vyber `L2_citations` → Add
4. Opakuj pro `L2_answer_texts`

### 4. Doporučené worksheets

| Sheet | Typ | Dimenze | Metrika |
|---|---|---|---|
| Visibility timeline | Line chart | `snapshot_week` | `AVG(visibility_score)` |
| Brand comparison | Bar chart | `brand_name` | `visibility_score` |
| Topic breakdown | Heatmap | `topic_name` × `engine` | `AVG(visibility_score)` |
| AI Share of Voice | Pie chart | `brand_name` | `AVG(ai_share_of_voice)` |
| Citation domains | Bar chart | `domain` | `SUM(occurrences)` |

### 5. Doporučené filtry

- `topic_name` — Quick filter
- `engine` — Quick filter
- `is_own_brand` — Quick filter
- `snapshot_week` — Relative date filter
- `tag` — Quick filter (z joinu s `L2_search_term_tags`)

### 6. Tipy pro výkon

- V Tableau nastav **Extract** místo Live connection — data se stáhnou do Tableaua jednou a dotazy jsou rychlé
- Extract obnov ručně po každém denním pipeline runu, nebo nastav scheduled refresh v Tableau Server/Cloud

---

## Denní pipeline (připomenutí)

Aby byla data v BI vždy aktuální, musí každý den proběhnout v tomto pořadí:

```
1. rankscale_extract.py    →  raw_ tabulky  (GitHub Actions, 6:30 UTC)
2. transform_l1.sql        →  L1_ tabulky   (ručně nebo Keboola)
3. transform_l2.sql        →  L2_ tabulky   (ručně nebo Keboola)
4. Tableau Extract refresh →  aktuální data v reportu
```

Kroky 2 a 3 lze spustit v BigQuery konzoli nebo přidat jako scheduled query.
