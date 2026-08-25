# Rankscale → BigQuery

Denní pipeline která tahá data z Rankscale Metrics API do BigQuery.
Existují dva skripty — liší se přístupem k transformaci dat.

---

## Dva skripty — který použít?

| | `rankscale_extract.py` ✅ aktivní | `rankscale_etl.py` archiv |
|---|---|---|
| **Přístup** | EL — čistý extract, žádná logika | ETL — transformace přímo v Pythonu |
| **BQ tabulky** | `raw_*` (append každý den) | `brands`, `search_terms`, `brand_snapshots`, ... |
| **Transformace** | Keboola | Python script |
| **Workflow** | `extract.yml` (6:30 UTC) | `etl.yml` (6:00 UTC) |
| **Složitost** | ~200 řádků | ~600 řádků |

**Používej `rankscale_extract.py`.** Starý ETL je zachován pro případ potřeby, ale není aktivně udržován.

---

## Co extract stahuje

| Endpoint | Raw tabulka |
|----------|-------------|
| GET /v1/metrics/brands | `raw_brands` |
| GET /v1/metrics/search-terms | `raw_search_terms` |
| POST /v1/metrics/search-terms-report | `raw_brand_snapshots` |
| POST /v1/metrics/search-terms-report (answer texts) | `raw_answer_texts` |
| POST /v1/metrics/citations | `raw_citations` |

Každý run **APPENDuje** nové řádky — historická data zůstávají. Dedup, is_active flagy a joiny řeší Keboola.

## BigQuery tabulky

**Dataset:** `libor-matejkacz.RankScaleDashboard`

| Tabulka | Popis |
|---------|-------|
| `raw_brands` | Snapshot brandů per ETL run |
| `raw_search_terms` | Snapshot search termů (prompt × engine) per ETL run |
| `raw_brand_snapshots` | Metriky per brand per search term — **hlavní tabulka** |
| `raw_answer_texts` | Raw texty AI odpovědí |
| `raw_citations` | Citované domény a URL |

Detailní popis tabulek: `docs/bigquery-data-model.md`
DDL: `sql/schema_raw.sql`

---

## Nastavení

### 1. GitHub Secrets

V repozitáři jdi na **Settings → Secrets and variables → Actions → New repository secret**
a přidej tyto 4 secrets:

| Secret | Hodnota |
|--------|---------|
| `RANKSCALE_API_KEY` | Tvůj Rankscale API klíč (začíná `rk_`) |
| `GCP_PROJECT` | ID GCP projektu, např. `libor-matejkacz` |
| `BQ_DATASET` | Název datasetu, např. `RankScaleDashboard` |
| `GCP_SA_JSON` | JSON obsah service account klíče (viz níže) |

### 2. GCP Service Account

1. GCP Console → **IAM & Admin → Service Accounts → Create Service Account**
2. Název: `rankscale-etl`
3. Role: **BigQuery Data Editor** + **BigQuery Job User**
4. Po vytvoření: **Keys → Add Key → JSON** → stáhni soubor
5. Obsah JSON souboru vlož celý jako hodnotu secretu `GCP_SA_JSON`

### 3. Spuštění

- **Automaticky**: každý den v 6:30 UTC
- **Ručně**: GitHub → Actions → "Rankscale → BigQuery RAW Extract" → **Run workflow**
- **Backfill**: při ručním spuštění lze zadat `time_frame` (např. `1y` pro celou historii)

---

## Lokální vývoj

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

export RANKSCALE_API_KEY=rk_tvuj_klic
export GCP_PROJECT=libor-matejkacz
export BQ_DATASET=RankScaleDashboard
gcloud auth application-default login

python src/rankscale_extract.py
```

## Časové okno dat

Script stahuje posledních `7d` dat (výchozí hodnota `TIME_FRAME`).
Pro backfill historických dat spusť ručně z GitHub Actions a zvol `time_frame = 1y`.

---

## Alternativa: nasazení na GCP (Cloud Run Job + Cloud Scheduler)

Pro případ, že nechceš záviset na GitHub Actions, existuje verze pro Cloud Run Job
ve složce [`GCP/`](GCP/README.md) — stejná extract logika, ale autentizace k BigQuery
jde přes service account přiřazený přímo k jobu (žádný `GCP_SA_JSON` secret) a
spouští se z Cloud Scheduleru místo GitHub Actions cronu.

Kompletní postup nasazení (příprava projektu, service account, Secret Manager,
build image, Cloud Scheduler): viz **[GCP/README.md](GCP/README.md)**.
