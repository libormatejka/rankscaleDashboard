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

## Dva druhy proměnných — nepliť si je

V krocích níže se objevují dva odlišné typy proměnných:

| | Shell proměnné (`$GCP_PROJECT`, `$REGION`, `$REPO`, `$SA_NAME`) | Env proměnné kontejneru (`--set-env-vars`, `--set-secrets`) |
|---|---|---|
| **Kde se nastavují** | `export` v tvém terminálu (krok 1) | přímo v příkazu `gcloud run jobs create/update` |
| **K čemu slouží** | jen jako zkratky pro `gcloud` příkazy, aby ses nemusel opakovat | proměnné, které **uvidí samotný Python skript** uvnitř kontejneru za běhu |
| **Kdy zmizí** | při zavření terminálu / nové kartě Cloud Shellu / restartu session | jsou trvale uložené v definici Cloud Run Jobu, dokud job neupravíš znovu |

**Než spustíš jakýkoliv příkaz s `$PROMĚNNOU`, over si ve stejném terminálu:**

```bash
echo $GCP_PROJECT $REGION $REPO $SA_NAME
```

Pokud je výstup prázdný, `export` řádky z kroku 1 spadly (nová session) — spusť je znovu.

### Kam nastavit cílový GCP projekt a BigQuery dataset

Toto je to hlavní, co určuje, **kam se data reálně zapisují** — a je to jediné místo
v celém návodu, kde nastavuješ hodnotu v souboru místo v příkazové řádce:

- Otevři [`env.yaml`](env.yaml) v této složce a uprav dva řádky:
  ```yaml
  GCP_PROJECT: rankscale
  BQ_DATASET: RankScaleDashboard
  ```
  Skript je čte jako `os.environ["GCP_PROJECT"]` / `os.environ["BQ_DATASET"]`
  (viz `rankscale_extract_gcp.py`, funkce `tbl()` — tabulky jsou `{GCP_PROJECT}.{BQ_DATASET}.raw_*`).
- Při vytváření jobu (krok 5) se soubor předá přes `--env-vars-file=env.yaml` —
  nic dalšího psát nemusíš.
- Pokud chceš cíl **později změnit** (jiný projekt/dataset), stačí upravit `env.yaml`
  a spustit:
  ```bash
  gcloud run jobs update rankscale-extract --region=$REGION --env-vars-file=env.yaml
  ```
- Service account jobu (`$SA_NAME`) musí mít `roles/bigquery.dataEditor` + `roles/bigquery.jobUser`
  **v tom projektu, kam se zapisuje** (krok 2) — pokud v `env.yaml` přepneš `GCP_PROJECT`
  na jiný projekt, potřebuješ IAM binding zopakovat i tam.

---

## 1. Příprava GCP projektu

Projekt musí mít zapnuté **billing** (Cloud Build / Artifact Registry / Cloud Run
bez něj nejdou zapnout) — over v Cloud Console **Billing**, že je k projektu
připojený účet.

```bash
export GCP_PROJECT=rankscale         # skutečné project ID cílového projektu (ne "hezký" název)
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

**Ověř, že se aktivní projekt opravdu přepnul** — tohle je nejčastější zdroj problémů
při přesunu na jiný projekt (service account nebo IAM binding pak nenápadně vzniknou
ve starém projektu):

```bash
gcloud config get-value project
```

Musí to vypsat přesně hodnotu `$GCP_PROJECT`. Pokud ne, `export` proběhl ve starší
kartě/session a tahle nová o něm neví — nastav `export GCP_PROJECT=...` znovu tady.

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

Ověř, že SA opravdu vznikl v `$GCP_PROJECT` (ne v jiném projektu, kde jsi `gcloud`
používal dřív):

```bash
gcloud iam service-accounts describe "${SA_NAME}@${GCP_PROJECT}.iam.gserviceaccount.com"
```

Pokud vrátí chybu "NOT_FOUND", SA vznikl jinde — zkontroluj `gcloud config get-value project`
(viz krok 1) a založ ho znovu s aktivním správným projektem.

## 3. Rankscale API klíč do Secret Manageru

```bash
printf "%s" "rk_tvuj_skutecny_klic" | gcloud secrets create rankscale-api-key --data-file=-

gcloud secrets add-iam-policy-binding rankscale-api-key \
  --member="serviceAccount:${SA_NAME}@${GCP_PROJECT}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

**Nahraď `rk_tvuj_skutecny_klic` svým reálným Rankscale API klíčem** (Rankscale
dashboard → Settings/API, klíč začíná `rk_`) — ne placeholderem z tohoto návodu.
Ověř, že se uložil správně:

```bash
gcloud secrets versions access latest --secret=rankscale-api-key
```

Musí vypsat tvůj skutečný klíč. Pokud jsi secret omylem vytvořil s `echo` místo
`printf` (přidá na konec znak nového řádku, který Rankscale API odmítne jako
neplatný token), oprav to novou verzí:

```bash
gcloud secrets versions add rankscale-api-key --data-file=<(printf "%s" "rk_tvuj_skutecny_klic")
```

## 3b. BigQuery dataset a tabulky

**Bez tohoto kroku job nemá kam zapisovat — spustí se, ale spadne na zápisu do BigQuery**
(chyba typu `404 Not found: Dataset` nebo `Table not found`).

Skript (`bq_append`) očekává, že dataset a tabulky `raw_*` už existují — sám je nezakládá.
Produkční pipeline (GitHub Actions) píše do `libor-matejkacz.RankScaleDashboard`
(viz `../sql/extract1/schema_raw.sql`); tenhle GCP projekt je od ní oddělený, takže
potřebuje **vlastní** dataset a tabulky ve stejném `$GCP_PROJECT`, kam píše i `env.yaml`:

```bash
bq --project_id=$GCP_PROJECT mk --dataset --location=EU ${GCP_PROJECT}:RankScaleDashboard

bq query --project_id=$GCP_PROJECT --use_legacy_sql=false < schema_raw.sql
```

`schema_raw.sql` v této složce nemá project ID natvrdo zapsané (na rozdíl od
`../sql/extract1/schema_raw.sql`) — `bq query --project_id=$GCP_PROJECT` určí, do
kterého projektu se tabulky založí. Při přesunu na jiný projekt tedy stačí mít
správně nastavené `$GCP_PROJECT` (krok 1) a soubor spustit beze změny.

Pokud dataset už existuje (např. z předchozího pokusu), `bq mk` ohlásí
`Dataset already exists` — to je neškodné, pokračuj rovnou na `bq query`.

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

Cílový projekt a dataset (`GCP_PROJECT`, `BQ_DATASET`) se **nepíšou do příkazu ručně** —
jsou v souboru [`env.yaml`](env.yaml) ve stejné složce. Otevři ho a uprav podle sebe:

```yaml
GCP_PROJECT: rankscale
BQ_DATASET: RankScaleDashboard
```

Pak spusť (`--env-vars-file=env.yaml` soubor rovnou načte):

```bash
gcloud run jobs create rankscale-extract \
  --image="${REGION}-docker.pkg.dev/${GCP_PROJECT}/${REPO}/rankscale-extract:latest" \
  --region=$REGION \
  --service-account="${SA_NAME}@${GCP_PROJECT}.iam.gserviceaccount.com" \
  --env-vars-file=env.yaml \
  --set-secrets="RANKSCALE_API_KEY=rankscale-api-key:latest" \
  --max-retries=1 \
  --task-timeout=1200
```

Proměnné:

| Proměnná | Kde se nastavuje |
|---|---|
| `GCP_PROJECT`, `BQ_DATASET` | v souboru `env.yaml` (uprav a ulož, žádný `gcloud` flag nepotřebuješ psát ručně) |
| `RANKSCALE_API_KEY` | Secret Manager, mountnutý přes `--set-secrets` (krok 3) |
| `BACKFILL_WEEKS` | volitelné, jen pro backfill, viz níže — nastavuje se zvlášť při konkrétním spuštění |

Když později změníš `env.yaml` (jiný projekt/dataset), aplikuješ to na existující job příkazem:

```bash
gcloud run jobs update rankscale-extract --region=$REGION --env-vars-file=env.yaml
```

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

## Troubleshooting — reálné chyby, na které lze narazit

| Chyba v logu | Příčina | Oprava |
|---|---|---|
| `requests.exceptions.HTTPError: 401 ... rankscale.ai/v1/metrics/brands` | V Secret Manageru je pořád placeholder `rk_tvuj_klic` (nebo klíč s nadbytečným `\n` z `echo`) | `gcloud secrets versions access latest --secret=rankscale-api-key` — over hodnotu; oprav přes `gcloud secrets versions add ...` (krok 3) |
| `google.api_core.exceptions.Forbidden: 403 ... User does not have bigquery.jobs.create permission in project X` | Service account byl založený/oprávněný v **jiném** projektu, než do kterého `env.yaml` píše (typicky když `gcloud config get-value project` v tu chvíli ukazoval na jiný projekt, než jaký máš v `$GCP_PROJECT`) | `gcloud iam service-accounts describe "${SA_NAME}@${GCP_PROJECT}.iam.gserviceaccount.com"` ověří, kde SA vznikl; `gcloud projects get-iam-policy $GCP_PROJECT --flatten="bindings[].members" --filter="bindings.role:roles/bigquery.jobUser"` ověří, komu je role přiřazená. Chybějící binding lze přidat i mezi projekty (SA z projektu A lze oprávnit v projektu B) — viz krok 2 |
| `404 Not found: Dataset ...` nebo `Table ... not found` | Dataset/tabulky v cílovém projektu ještě nevznikly | krok 3b — `bq mk` + `bq query < schema_raw.sql` |
| `-bash: --env-vars-file=env.yaml: command not found` | Víceřádkový příkaz se zalomením `\` se při kopírování rozdělil na samostatné řádky | Vlož celý příkaz najednou jako blok, nebo použij jednořádkovou verzi bez `\` |
| `bq: command not found` / `xxd: command not found` | Cloud Shell nemá `xxd` (a některé nástroje) předinstalované | Použij `od -c` místo `xxd` |
| Prázdný výstup `echo $GCP_PROJECT ...` | `export` proměnné z kroku 1 platí jen v aktuální session/kartě Cloud Shellu | Spusť `export` řádky z kroku 1 znovu v aktuálním terminálu |

## Lokální test image

```bash
cd GCP
docker build -t rankscale-extract-local .

docker run --rm \
  -e RANKSCALE_API_KEY=rk_tvuj_klic \
  -e GCP_PROJECT=rankscale \
  -e BQ_DATASET=RankScaleDashboard \
  -v ~/.config/gcloud:/root/.config/gcloud:ro \
  rankscale-extract-local
```

(Mount `~/.config/gcloud` funguje jen pokud máš lokálně `gcloud auth application-default login`
a image běží jako root — pro rychlý lokální test stačí, pro produkci se auth řeší
přes service account Cloud Run Jobu, viz výše.)
