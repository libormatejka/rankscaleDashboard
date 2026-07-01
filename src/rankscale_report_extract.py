"""
Rankscale → BigQuery  |  Report Extract  (L0 vrstva)
Stahuje agregovaná data z /v1/metrics/report a ukládá je do:
  - raw_report_brand: timeline vlastního brandu + všech competitors
  - raw_report_topic: timeline vlastního brandu per topic

Jeden API call per brand vrátí timeline všech týdnů.
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
    return f"{GCP_PROJECT}.{BQ_DATASET}.raw_{name}"


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


def _parallel_to_rows(brand_id: str, brand_name: str, is_own_brand: bool, timestamps: list, metrics: dict) -> list[dict]:
    """Rozbalí parallel arrays (timestamps + metriky) do řádků."""
    rows = []
    for i, ts in enumerate(timestamps):
        rows.append({
            "owning_brand_id":  brand_id,
            "snapshot_date":    ts,
            "brand_name":       brand_name,
            "is_own_brand":     is_own_brand,
            "visibility_score": metrics.get("visibilityScore", [None])[i] if i < len(metrics.get("visibilityScore", [])) else None,
            "sentiment":        metrics.get("sentiment", [None])[i] if i < len(metrics.get("sentiment", [])) else None,
            "avg_position":     metrics.get("avgPosition", [None])[i] if i < len(metrics.get("avgPosition", [])) else None,
            "detection_rate":   metrics.get("detectionRate", [None])[i] if i < len(metrics.get("detectionRate", [])) else None,
            "top3":             metrics.get("top3", [None])[i] if i < len(metrics.get("top3", [])) else None,
            "mentions":         metrics.get("mentions", [None])[i] if i < len(metrics.get("mentions", [])) else None,
            "citations":        metrics.get("citations", [None])[i] if i < len(metrics.get("citations", [])) else None,
        })
    return rows


def extract_report(client: bigquery.Client, brand_id: str, brand_name: str, iso_start: str, iso_end: str) -> None:
    log.info(f"── report  (brand={brand_id}, {iso_start} → {iso_end})")

    data = api_post("/v1/metrics/report", {
        "brandId":        brand_id,
        "isoStartDate":   iso_start,
        "isoEndDate":     iso_end,
        "aggregation":    "weekly",
        "selectedTopic":  "all",
        "selectedTags":   "all",
        "selectedEngine": "all",
        "selectedQuery":  "all",
    })

    d = data["data"]
    rows = []

    # Vlastní brand — z ownBrandMetrics.historicalData
    own = d.get("ownBrandMetrics", {})
    hist = own.get("historicalData", {})
    # Preferujeme weekly, fallback na daily (API vrací data dle frekvence snapshotů)
    period_data = hist.get("weekly") or hist.get("daily") or {}
    timestamps = period_data.get("timestamps", [])

    if timestamps:
        own_metrics = {k: v for k, v in period_data.items() if k != "timestamps" and k != "brandNotFound"}
        rows.extend(_parallel_to_rows(brand_id, own.get("name", brand_name), True, timestamps, own_metrics))
        log.info(f"    own brand: {len(timestamps)} týdnů")
    else:
        log.info("    own brand: žádná historická data")

    # Competitors — z competitorTimeSeriesData
    comp_ts_data = d.get("competitorTimeSeriesData", {})
    comp_period = comp_ts_data.get("weekly") or comp_ts_data.get("daily") or {}
    comp_timestamps = comp_period.get("timestamps", [])
    competitors = comp_period.get("competitors", [])

    for comp in competitors:
        if comp_timestamps:
            rows.extend(_parallel_to_rows(
                brand_id,
                comp.get("name"),
                comp.get("isOwnBrand", False),
                comp_timestamps,
                comp.get("metrics", {}),
            ))

    log.info(f"    competitors: {len(competitors)}, celkem řádků: {len(rows)}")
    bq_append(client, tbl("report_brand"), rows)


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
        "aggregation":    "weekly",
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

    bq_append(client, tbl("report_topic_brand"), rows)


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    today = date.today()

    if BACKFILL_START:
        iso_start = BACKFILL_START
        mode = f"BACKFILL od {iso_start}"
    else:
        iso_start = (today - timedelta(days=90)).isoformat()
        mode = "denní run (posledních 90 dní)"

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
            extract_report(client, brand_id, brand_name, iso_start, iso_end)

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
