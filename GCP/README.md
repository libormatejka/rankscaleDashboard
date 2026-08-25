# Rankscale → BigQuery — nasazení na GCP (Cloud Run Job)

Alternativa k GitHub Actions workflow (`../.github/workflows/extract1.yml`).
Stejná extract logika jako `../src/rankscale_extract.py`, ale spouští se jako
**Cloud Run Job** na cronu z **Cloud Scheduleru**, ne z GitHub Actions.

---

## Proč jiný skript

`rankscale_extract_gcp.py` je odvozený od `../src/rankscale_extract.py` s jedním
rozdílem v autentizaci k BigQuery:

| | GitHub Actions (`rankscale_extract.py`) | Cloud Run Job (`rankscale_extract_gcp.py`) |
|---|---|---|
| **BigQuery auth** | JSON klíč service accountu ze secretu `GCP_SA_JSON` | Application Default Credentials — service account je přiřazený přímo k jobu, žádný klíč se nikam nekopíruje |
| **Rankscale API klíč** | GitHub Secret `RANKSCALE_API_KEY` | GCP Secret Manager, namountovaný jako env proměnná |
| **Chybové chování** | log chyby, pokračuje dál | log chyby, na konci `sys.exit(1)` pokud selhal alespoň jeden brand → Cloud Run execution se označí jako **Failed** |
| **Spouštěč** | `schedule:` v `.yml` workflow | Cloud Scheduler → HTTP trigger na Cloud Run Jobs API |

Business logika (endpoints, transformace řádků, BQ append, skip-if-no-new-data)
je 1:1 stejná — viz hlavní [README](../README.md) pro popis tabulek a datového modelu.

---

## Obsah složky

| Soubor | Účel |
|---|---|
| `rankscale_extract_gcp.py` | samotný extract skript |
| `Dockerfile` | image pro Cloud Run Job |
| `.dockerignore` | vynechá README z buildu |
| `requirements.txt` | Python závislosti (subset — bez `google-auth`, ten už táhne `google-cloud-bigquery`) |

---

## 1. Příprava GCP projektu

```bash
export GCP_PROJECT=libor-matejkacz
export REGION=europe-west3          # nebo jiný region blízko tebe
export REPO=rankscale
export SA_NAME=rankscale-extract-job

gcloud config set project $GCP_PROJECT

gcloud services enable \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  bigquery.googleapis.com \
  cloudbuild.googleapis.com
```

## 2. Service account pro job

Samostatný SA jen pro tento job — žádné šířeji oprávněné účty.

```bash
gcloud iam service-accounts create $SA_NAME \
  --display-name="Rankscale Extract Cloud Run Job"

gcloud projects add-iam-policy-binding $GCP_PROJECT \
  --member="serviceAccount:${SA_NAME}@${GCP_PROJECT}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $GCP_PROJECT \
  --member="serviceAccount:${SA_NAME}@${GCP_PROJECT}.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"
```

## 3. Rankscale API klíč do Secret Manageru

```bash
printf "rk_tvuj_klic" | gcloud secrets create rankscale-api-key --data-file=-

gcloud secrets add-iam-policy-binding rankscale-api-key \
  --member="serviceAccount:${SA_NAME}@${GCP_PROJECT}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## 4. Build image a push do Artifact Registry

Build se spouští **z této složky** (`GCP/`), aby `Dockerfile` a `COPY` cesty seděly:

```bash
cd GCP

gcloud artifacts repositories create $REPO \
  --repository-format=docker \
  --location=$REGION

gcloud builds submit \
  --tag "${REGION}-docker.pkg.dev/${GCP_PROJECT}/${REPO}/rankscale-extract:latest"
```

## 5. Vytvoření Cloud Run Job

```bash
gcloud run jobs create rankscale-extract \
  --image="${REGION}-docker.pkg.dev/${GCP_PROJECT}/${REPO}/rankscale-extract:latest" \
  --region=$REGION \
  --service-account="${SA_NAME}@${GCP_PROJECT}.iam.gserviceaccount.com" \
  --set-env-vars="GCP_PROJECT=${GCP_PROJECT},BQ_DATASET=RankScaleDashboard" \
  --set-secrets="RANKSCALE_API_KEY=rankscale-api-key:latest" \
  --max-retries=1 \
  --task-timeout=1200
```

Proměnné:

| Env var | Hodnota |
|---|---|
| `GCP_PROJECT` | ID GCP projektu |
| `BQ_DATASET` | Dataset s `raw_*` tabulkami, např. `RankScaleDashboard` |
| `RANKSCALE_API_KEY` | mountnutý ze Secret Manageru, ne plain env var |
| `BACKFILL_WEEKS` | volitelné, jen pro backfill (viz níže) |

### Ruční spuštění / test

```bash
gcloud run jobs execute rankscale-extract --region=$REGION
```

### Backfill

Jednorázově přepíše env proměnnou jen pro tento konkrétní run:

```bash
gcloud run jobs execute rankscale-extract --region=$REGION \
  --update-env-vars="BACKFILL_WEEKS=52"
```

## 6. Denní spouštění přes Cloud Scheduler

```bash
SA_EMAIL="${SA_NAME}@${GCP_PROJECT}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding $GCP_PROJECT \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.invoker"

gcloud scheduler jobs create http rankscale-extract-daily \
  --location=$REGION \
  --schedule="30 6 * * *" \
  --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${GCP_PROJECT}/jobs/rankscale-extract:run" \
  --http-method=POST \
  --oauth-service-account-email="$SA_EMAIL" \
  --time-zone="UTC"
```

Stejný čas jako GitHub Actions workflow (6:30 UTC) — pokud běží oba, spusť
jen jeden z nich, jinak se data budou appendovat 2×.

## 7. Aktualizace image po změně kódu

```bash
cd GCP

gcloud builds submit \
  --tag "${REGION}-docker.pkg.dev/${GCP_PROJECT}/${REPO}/rankscale-extract:latest"

gcloud run jobs update rankscale-extract \
  --image="${REGION}-docker.pkg.dev/${GCP_PROJECT}/${REPO}/rankscale-extract:latest" \
  --region=$REGION
```

---

## Monitoring a logy

- **Cloud Console → Cloud Run → Jobs → rankscale-extract → Executions** — historie běhů, exit kódy
- **Cloud Logging** (`resource.type="cloud_run_job"`) — stdout/stderr ze skriptu
- Neúspěšný brand (chyba API/BQ) se loguje, ale extract pokračuje na dalších brandech;
  pokud selhal **alespoň jeden**, celý job skončí s `exit(1)` → execution je označená **Failed**
  a lze na to navázat alert v Cloud Monitoringu (`Cloud Run Job Execution Failed`).

## Lokální test image

```bash
cd GCP
docker build -t rankscale-extract-local .

docker run --rm \
  -e RANKSCALE_API_KEY=rk_tvuj_klic \
  -e GCP_PROJECT=libor-matejkacz \
  -e BQ_DATASET=RankScaleDashboard \
  -v ~/.config/gcloud:/root/.config/gcloud:ro \
  rankscale-extract-local
```

(Mount `~/.config/gcloud` funguje jen pokud máš lokálně `gcloud auth application-default login`
a image běží jako root — pro rychlý lokální test stačí, pro produkci se auth řeší
přes service account Cloud Run Jobu, viz výše.)
