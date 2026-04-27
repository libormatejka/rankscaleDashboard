# Rankscale → BigQuery ETL – Kontext projektu

## Co jsme postavili

Automatický denní pipeline který tahá AI visibility data z Rankscale Metrics API
a ukládá je do BigQuery pro vlastní reporting.

---

## Stav k 2026-04-27

### ✅ Hotovo
- Navrženo a odsouhlaseno BigQuery schema (9 tabulek)
- Všechny tabulky **fyzicky vytvořeny** v BQ: `libor-matejkacz.RankscaleMetrics`
- ETL Python skript funkční pro Krok 1 (dim_brands)
- GitHub Actions workflow nastaven a spouští se
- GCP Service Account oprávnění vyřešena (BigQuery Data Editor + Job User na úrovni projektu)
- Odladěny BQ-specifické problémy: streaming buffer, reserved keyword `interval`, DEFAULT hodnoty

### 🔧 Rozpracováno – PŘÍŠTÍ SESSION ZAČNI ZDE
ETL skript (v5) selhal na **Kroku 2 – dim_search_terms** s `KeyError: 'query'`.

Přidán debug log – po spuštění v5 se v GitHub Actions logu zobrazí:
```
→ DEBUG search term klíče: ['id', 'xxxxx', ...]
```
**Pošli tento řádek Claudovi** → opraví všechna pole najednou a vydá v6.

Poté bude potřeba projet stejně Kroky 3–7 a ověřit že field names sedí.

---

## Architektura

### BigQuery dataset
```
libor-matejkacz.RankscaleMetrics
```

### 9 tabulek a jejich zdroje

| Tabulka | Endpoint | Metoda zápisu |
|---|---|---|
| `dim_brands` | GET /v1/metrics/brands | WRITE_TRUNCATE (celá tabulka) |
| `dim_search_terms` | GET /v1/metrics/search-terms?brandId=ID | WRITE_TRUNCATE (celá tabulka) |
| `fact_report_timeseries` | POST /v1/metrics/report → timeSeries[] | Partition overwrite per date |
| `fact_report_by_engine` | POST /v1/metrics/report → byEngine{} | Partition overwrite per snapshot_date |
| `fact_search_term_snapshots` | POST /v1/metrics/search-terms-report | Partition overwrite per snapshot_date |
| `fact_answer_texts` | POST /v1/metrics/search-terms-report (includeAnswerTexts:true) | Append + dedup na execution_id |
| `fact_sentiment_timeseries` | POST /v1/metrics/sentiment → timeSeries[] | Partition overwrite per date |
| `fact_sentiment_by_engine` | POST /v1/metrics/sentiment → byEngine{} | Partition overwrite per snapshot_date |
| `fact_citations` | POST /v1/metrics/citations | Partition overwrite per last_seen |

### Klíčová designová rozhodnutí

**Proč load jobs místo insert_rows_json?**
BQ streaming insert plní "streaming buffer" – dokud se nevyprázdní (hodiny),
nelze na daných řádcích dělat DELETE ani partition overwrite. Load jobs
zapisují přímo do table storage – žádný buffer, žádný problém.

**Proč WRITE_TRUNCATE pro dim tabulky?**
dim_brands má 1 záznam, dim_search_terms má ~456 záznamů. Jsou malé,
mění se zřídka, nejjednodušší je celou tabulku nahradit čerstvými daty.

**Proč partition overwrite pro fact tabulky?**
Každý run táhne `TIME_FRAME = "7d"` dat (překryv je záměrný jako pojistka).
Partition overwrite přepíše jen dotčené dny, historická data zůstanou nedotčena.

**Proč sentiment score jako FLOAT64 (0–1), ne STRING?**
API vrací `0.72`, ne `"positive"`. String label (`"positive"`) vrací API
jen v `byEngine[].label` a `overall.label` – ne v timeSeries.

**Proč topic jako STRING, ne FK na dim tabulku?**
API vrací topic jako prostý string (`"Product Comparisons"`), bez topic ID.
Žádná separátní dim_topics tabulka není potřeba.

---

## ETL skript

### Umístění v repozitáři
```
rankscaleDashboard/
├── src/rankscale_etl.py       ← hlavní skript
├── requirements.txt
├── README.md
└── .github/workflows/etl.yml  ← cron 6:00 UTC = 7:00 CET
```

### GitHub Secrets (všechny nastaveny)
| Secret | Popis |
|---|---|
| `RANKSCALE_API_KEY` | Rankscale API klíč (začíná `rk_`) |
| `GCP_PROJECT` | `libor-matejkacz` |
| `BQ_DATASET` | `RankscaleMetrics` |
| `GCP_SA_JSON` | JSON obsah GCP service account klíče |

### Konstanty v skriptu
```python
TIME_FRAME  = "7d"    # kolik dat se táhne per run (překryv = bezpečný)
AGGREGATION = "daily"
```

### Helpery (jak funguje zápis do BQ)
```python
load_truncate(client, table("dim_..."), rows)
# → WRITE_TRUNCATE, nahradí celou tabulku

load_partitions(client, table("fact_..."), rows, date_col="date")
# → overwrite per partition, jeden load job per unikátní datum

load_append_dedup(client, table("fact_answer_texts"), rows, dedup_key="execution_id")
# → SELECT existující execution_id → append jen nových
```

---

## Rankscale API

### Base URL
```
https://rankscale.ai
```

### Autentizace
```
Authorization: Bearer rk_...
```

### Endpointy
```
GET  /v1/metrics/brands
GET  /v1/metrics/search-terms?brandId=ID
POST /v1/metrics/report
POST /v1/metrics/search-terms-report
POST /v1/metrics/sentiment
POST /v1/metrics/citations
```

### Zjištěné odchylky API vs dokumentace
| Dokumentace říká | API reálně vrací | Kde |
|---|---|---|
| `brands[].id` | ✅ sedí | GET /brands |
| `searchTerms[].brandId` | ❌ pole neexistuje – brand_id se doplňuje z parametru volání | GET /search-terms |
| `searchTerms[].query` | ❌ KeyError – reálný název pole NEZNÁME (debug v5 to zjistí) | GET /search-terms |

### Brand ID tvého brandy
```
E5GAVmqco65u7Smx3hso
```

### Rate limit
200 req/min → skript čeká 0.4s mezi voláními (`RATE_LIMIT_SLEEP`)

---

## Odladěné BQ chyby (pro případ že se vrátí)

### `DEFAULT CURRENT_TIMESTAMP()` v DDL
BQ nepodporuje DEFAULT hodnoty v CREATE TABLE.
Řešení: odstranit, plnit `loaded_at` v ETL skriptu jako `NOW`.

### Reserved keyword `interval`
BQ má `INTERVAL` jako rezervované slovo.
Řešení: obalit backticky → `` `interval` ``

### `Permission bigquery.tables.create denied`
Service account neměl roli na úrovni projektu (měl ji jen na datasetu).
Řešení: GCP Console → IAM → přidat `BigQuery Data Editor` + `BigQuery Job User` na projekt.

### `UPDATE or DELETE would affect rows in the streaming buffer`
Nastane pokud použiješ `insert_rows_json` a pak DELETE na stejnou tabulku.
Řešení: nikdy nepoužívat `insert_rows_json` – vždy load jobs.

---

## Soubory vytvořené v tomto projektu

| Soubor | Popis |
|---|---|
| `rankscale_bigquery_ddl_v3.sql` | Finální DDL pro vytvoření všech 9 tabulek |
| `rankscale_metrics_api_schema_final.sql` | Schema + views + ETL logika (referenční) |
| `Rankscale_Metrics_API.postman_collection.json` | Postman collection |
| `rankscale-bruno.zip` | Bruno collection |
| `rankscale-etl-v5.zip` | Aktuální verze ETL skriptu |

---

## Co bude dál (backlog)

1. **Doladit ETL v6** – opravit field names po debug výstupu z v5
2. **Ověřit všechny kroky 3–7** – projet response strukturu pro každý endpoint
3. **Vytvořit BQ Views** pro reporting (připraveny v `rankscale_metrics_api_schema_final.sql`)
4. **Napojit Looker Studio** na BQ views
5. **Zvážit historický backfill** – spustit ETL s `TIME_FRAME = "1y"` pro načtení celé historie