# Rankscale → BigQuery ETL

Denní ETL který tahá data z Rankscale Metrics API a ukládá je do BigQuery.
Běží automaticky každý den v 6:00 UTC přes GitHub Actions.

## Co načítá

| Krok | Endpoint | BQ tabulka |
|------|----------|------------|
| 1 | GET /v1/metrics/brands | `brands` |
| 2 | GET /v1/metrics/search-terms | `search_terms` |
| 3 | POST /v1/metrics/search-terms-report | `brand_snapshots` |
| 4 | POST /v1/metrics/search-terms-report (answer texts) | `answer_texts` |
| 5 | POST /v1/metrics/citations | `citations` |

Kroky 3–5 se spustí jen pokud Rankscale má novější data než BigQuery (freshness check).

## BigQuery tabulky

**Dataset:** `libor-matejkacz.RankScaleDashboard`

| Tabulka | Popis | Strategie zápisu |
|---------|-------|-----------------|
| `brands` | Číselník vlastních brandů | TRUNCATE |
| `search_terms` | Číselník dotazů (query × engine) | TRUNCATE |
| `brand_snapshots` | Metriky per brand per search term per týden — **hlavní tabulka** | Partition overwrite |
| `answer_texts` | Raw texty AI odpovědí | Append + dedup |
| `citations` | Citované domény a URL per query a engine | Partition overwrite |

Detailní popis tabulek a příklady SQL: `docs/bigquery-data-model.md`

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
export BQ_DATASET=RankScaleDashboard
# GCP_SA_JSON není potřeba lokálně pokud máš Application Default Credentials:
gcloud auth application-default login

# Spusť
python src/rankscale_etl.py
```

## Časové okno dat

Skript tahá vždy posledních `7d` dat (konstanta `TIME_FRAME` v ETL skriptu).
Partition overwrite a dedup zajistí že duplikáty nevzniknou.
Pokud chceš načíst historická data zpětně, změň `TIME_FRAME` na `30d` nebo `3m`
a spusť ručně.
