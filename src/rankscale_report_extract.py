"""
Rankscale → BigQuery  |  Report Extract  (L0 vrstva)
Stahuje agregovaná data z /v1/metrics/report a ukládá je do:
  - L0_report_table: timeline vlastního brandu + competitors per topic

Jeden API call per topic per brand vrátí timeline všech týdnů.
API samo určuje které týdny mají data — žádná iterace přes týdny.

Rozdíl oproti rankscale_extract.py:
  - Žádný detail per prompt — jen agregát za celý brand / topic
  - Čistší timeline bez děr a duplicit
  - Vhodný pro brand-level a topic-level trend analýzu

Režimy spuštění:
  - Denní run:  stáhne posledních 90 dní (zachytí poslední 3 měsíce)
  - Backfill:   BACKFILL_START=YYYY-MM-DD, stáhne od tohoto data do dnes
"""

import io
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone

import requests
from google.cloud import bigquery
from google.oauth2 import service_account

# ── Konfigurace ────────────────────────────────────────────────────────────────
API_BASE       = "https://rankscale.ai"
API_KEY        = os.environ["RANKSCALE_API_KEY"]
GCP_PROJECT    = os.environ["GCP_PROJECT"]
BQ_DATASET     = os.environ["BQ_DATASET"]
BACKFILL_START = os.environ.get("BACKFILL_START")  # YYYY-MM-DD, prázdné = denní run

NOW = datetime.now(timezone.utc).isoformat()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ── BigQuery helpers ───────────────────────────────────────────────────────────
def make_client() -> bigquery.Client:
    sa_json = os.environ.get("GCP_SA_JSON")
    if sa_json:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(sa_json),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return bigquery.Client(project=GCP_PROJECT, credentials=creds)
    return bigquery.Client(project=GCP_PROJECT)


def tbl(name: str) -> str:
    return f"{GCP_PROJECT}.{BQ_DATASET}.{name}"


def bq_append(client: bigquery.Client, table: str, rows: list[dict]) -> None:
    if not rows:
        log.info(f"    → {table.split('.')[-1]}: 0 řádků, přeskakuji")
        return
    for row in rows:
        row["etl_loaded_at"] = NOW
    ndjson = "\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in rows)
    cfg = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        autodetect=False,
    )
    client.load_table_from_file(
        io.BytesIO(ndjson.encode()),
        table,
        job_config=cfg,
    ).result()
    log.info(f"    → {table.split('.')[-1]}: {len(rows)} řádků zapsáno")


# ── Rankscale API ──────────────────────────────────────────────────────────────
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def api_get(path: str, params: dict | None = None) -> dict:
    r = requests.get(f"{API_BASE}{path}", headers=HEADERS, params=params, timeout=120)
    r.raise_for_status()
    return r.json()


def api_post(path: str, body: dict) -> dict:
    r = requests.post(f"{API_BASE}{path}", headers=HEADERS, json=body, timeout=120)
    r.raise_for_status()
    return r.json()


# ── Extract ────────────────────────────────────────────────────────────────────
def extract_brands() -> list[dict]:
    data = api_get("/v1/metrics/brands", {"limit": 1000})
    brands = data["data"]["brands"]
    log.info(f"    {len(brands)} brand(ů): {[b['id'] for b in brands]}")
    return brands


def fetch_topics(brand_id: str) -> list[dict]:
    data = api_get("/v1/metrics/topics", {"brandRef": brand_id})
    topics = data["data"]["topics"]
    # Přeskočíme topicy bez přiřazených search termů
    active = [t for t in topics if t.get("searchTermIds")]
    log.info(f"    topics: {len(active)} aktivních z {len(topics)}")
    return active


def extract_report_by_topic(
    client: bigquery.Client,
    brand_id: str,
    brand_name: str,
    topic_id: str,
    topic_name: str,
    iso_start: str,
    iso_end: str,
) -> None:
    log.info(f"    topic '{topic_name}' ({topic_id})")
    data = api_post("/v1/metrics/report", {
        "brandId":        brand_id,
        "isoStartDate":   iso_start,
        "isoEndDate":     iso_end,
        "aggregation":    "daily",
        "filters":        {"topicId": topic_id},
        "selectedEngine": "all",
        "selectedQuery":  "all",
    })

    d = data["data"]
    rows = []

    def safe_get(arr: list, i: int):
        return arr[i] if i < len(arr) else None

    def parse_period(period_data: dict, b_name: str, is_own: bool) -> list[dict]:
        timestamps = period_data.get("timestamps", [])
        out = []
        for i, ts in enumerate(timestamps):
            out.append({
                "owning_brand_id":  brand_id,
                "topic_id":         topic_id,
                "topic_name":       topic_name,
                "snapshot_date":    ts,
                "brand_name":       b_name,
                "is_own_brand":     is_own,
                "visibility_score": safe_get(period_data.get("visibilityScore", []), i),
                "sentiment":        safe_get(period_data.get("sentiment", []), i),
                "avg_position":     safe_get(period_data.get("avgPosition", []), i),
                "detection_rate":   safe_get(period_data.get("detectionRate", []), i),
                "top3":             safe_get(period_data.get("top3", []), i),
                "mentions":         safe_get(period_data.get("mentions", []), i),
                "citations":        safe_get(period_data.get("citations", []), i),
            })
        return out

    # Vlastní brand
    own = d.get("ownBrandMetrics", {})
    hist = own.get("historicalData", {})
    period_data = hist.get("weekly") or hist.get("daily") or {}
    rows.extend(parse_period(period_data, own.get("name", brand_name), True))

    # Competitors
    comp_ts = d.get("competitorTimeSeriesData", {})
    comp_period = comp_ts.get("weekly") or comp_ts.get("daily") or {}
    for comp in comp_period.get("competitors", []):
        metrics = comp.get("metrics", {})
        metrics["timestamps"] = comp_period.get("timestamps", [])
        rows.extend(parse_period(metrics, comp.get("name"), comp.get("isOwnBrand", False)))

    bq_append(client, tbl("L0_report_table"), rows)


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    today = date.today()

    if BACKFILL_START:
        iso_start = BACKFILL_START
        mode = f"BACKFILL od {iso_start}"
    else:
        iso_start = (today - timedelta(days=7)).isoformat()
        mode = "denní run (posledních 7 dní)"

    iso_end = today.isoformat()

    log.info("╔══════════════════════════════════════════╗")
    log.info(f"║  Rankscale Report Extract  [{mode}]")
    log.info(f"║  Období: {iso_start} → {iso_end}")
    log.info("╚══════════════════════════════════════════╝")

    client  = make_client()
    brands  = extract_brands()

    for brand in brands:
        brand_id   = brand["id"]
        brand_name = brand["name"]
        try:
            topics = fetch_topics(brand_id)
            for topic in topics:
                try:
                    extract_report_by_topic(
                        client, brand_id, brand_name,
                        topic["id"], topic["name"],
                        iso_start, iso_end,
                    )
                except Exception as e:
                    log.error(f"  Topic {topic['id']} selhal: {e}")

        except Exception as e:
            log.error(f"Brand {brand_id} selhal: {e}")

    log.info("╔══════════════════════════════════════════╗")
    log.info("║  Hotovo ✓                                 ║")
    log.info("╚══════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
