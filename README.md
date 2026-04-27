# Rankscale → BigQuery ETL

Denní ETL který tahá data z Rankscale Metrics API a ukládá je do BigQuery.
Běží automaticky každý den v 6:00 UTC přes GitHub Actions.

## Co načítá

| Krok | Endpoint | BQ tabulky |
|------|----------|------------|
| 1 | GET /v1/metrics/brands | dim_brands |
| 2 | GET /v1/metrics/search-terms | dim_search_terms |
| 3 | POST /v1/metrics/report | fact_report_timeseries, fact_report_by_engine |
| 4 | POST /v1/metrics/search-terms-report | fact_search_term_snapshots |
| 5 | POST /v1/metrics/search-terms-report (answer texts) | fact_answer_texts |
| 6 | POST /v1/metrics/sentiment | fact_sentiment_timeseries, fact_sentiment_by_engine |
| 7 | POST /v1/metrics/citations | fact_citations |

## Nastavení

### 1. GitHub Secrets

V repozitáři jdi na **Settings → Secrets and variables → Actions → New repository secret**
a přidej tyto 4 secrets:

| Secret | Hodnota |
|--------|---------|
| `RANKSCALE_API_KEY` | Tvůj Rankscale API klíč (začíná `rk_`) |
| `GCP_PROJECT` | ID GCP projektu, např. `libor-matejkacz` |
| `BQ_DATASET` | Název datasetu, např. `RankscaleMetrics` |
| `GCP_SA_JSON` | JSON obsah service account klíče (viz níže) |

### 2. GCP Service Account

1. GCP Console → **IAM & Admin → Service Accounts → Create Service Account**
2. Název: `rankscale-etl`
3. Role: **BigQuery Data Editor** + **BigQuery Job User**
4. Po vytvoření: **Keys → Add Key → JSON** → stáhni soubor
5. Obsah JSON souboru vlož celý jako hodnotu secretu `GCP_SA_JSON`

### 3. Spuštění

- **Automaticky**: každý den v 6:00 UTC
- **Ručně**: GitHub → Actions → "Rankscale → BigQuery ETL" → **Run workflow**

## Lokální vývoj

```bash
# Vytvoř virtuální prostředí
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Nainstaluj závislosti
pip install -r requirements.txt

# Nastav proměnné prostředí
export RANKSCALE_API_KEY=rk_tvuj_klic
export GCP_PROJECT=libor-matejkacz
export BQ_DATASET=RankscaleMetrics
# GCP_SA_JSON není potřeba lokálně pokud máš Application Default Credentials:
gcloud auth application-default login

# Spusť
python src/rankscale_etl.py
```

## Časové okno dat

Skript tahá vždy posledních `7d` dat (konstanta `TIME_FRAME` v ETL skriptu).
Překryv je záměrný – MERGE logika zajistí že duplikáty nevzniknou.
Pokud chceš načíst historická data zpětně, změň `TIME_FRAME` na `30d` nebo `3m`
a spusť ručně.
