"""
Rankscale → BigQuery  |  Tag Extract  (Extract 3, L0 vrstva)
Stahuje agregovaná data z /v1/metrics/report filtrovaná per tag a ukládá do:
  - L0_tag_table: timeline vlastního brandu + competitors per tag

Průběh per brand:
  1. GET /v1/metrics/search-terms  → seznam unikátních tagů
  2. POST /v1/metrics/report (filters.tags) → metriky per tag

Grain: owning_brand_id × tag × brand_name × snapshot_date

Režimy spuštění:
  - Denní run:  posledních 7 dní (zachytí aktuální týdenní snapshot)
  - Backfill:   BACKFILL_START + volitelně BACKFILL_END
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
BACKFILL_END   = os.environ.get("BACKFILL_END")    # YYYY-MM-DD, prázdné = dnes

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


def fetch_tag_topic_combinations(brand_id: str) -> list[tuple[str, str, str]]:
    """Vrátí unikátní kombinace (tag, topic_id, topic_name) pro daný brand.

    Logika:
      1. Stáhne topics → mapping searchTermId → (topic_id, topic_name)
      2. Stáhne search terms → každý term má tagy
      3. Zkříží: term → jeho tagy × jeho topic
    """
    # 1. Topics
    topics_data = api_get("/v1/metrics/topics", {"brandRef": brand_id})
    term_to_topic: dict[str, tuple[str, str]] = {}
    for t in topics_data["data"]["topics"]:
        for sid in (t.get("searchTermIds") or []):
            term_to_topic[sid] = (t["id"], t["name"])

    # 2. Search terms
    terms_data = api_get("/v1/metrics/search-terms", {"brandId": brand_id, "limit": 5000})
    terms = terms_data["data"]["searchTerms"]

    combinations: set[tuple[str, str, str]] = set()
    for term in terms:
        topic_info = term_to_topic.get(term.get("id") or term.get("searchTermId", ""))
        if not topic_info:
            continue
        raw = term.get("tags") or []
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = []
        for tag in raw:
            combinations.add((tag, topic_info[0], topic_info[1]))

    result = sorted(combinations)
    log.info(f"    tag×topic kombinace: {len(result)}")
    return result


def extract_report_by_tag(
    client: bigquery.Client,
    brand_id: str,
    brand_name: str,
    tag: str,
    topic_id: str,
    topic_name: str,
    iso_start: str,
    iso_end: str,
) -> None:
    log.info(f"    tag '{tag}' / topic '{topic_name}'")
    data = api_post("/v1/metrics/report", {
        "brandId":        brand_id,
        "isoStartDate":   iso_start,
        "isoEndDate":     iso_end,
        "aggregation":    "weekly",
        "filters":        {"tags": [tag], "topicId": topic_id},
        "selectedEngine": "all",
        "selectedQuery":  "all",
    })

    d = data["data"]
    rows = []

    def safe_get(arr: list, i: int):
        return arr[i] if i < len(arr) else None

    def pick_period(container: dict) -> dict:
        for key in ("weekly", "daily", "monthly", "hourly"):
            p = container.get(key, {})
            if p.get("timestamps"):
                return p
        return {}

    def parse_period(period_data: dict, b_name: str, is_own: bool) -> list[dict]:
        timestamps = period_data.get("timestamps", [])
        out = []
        for i, ts in enumerate(timestamps):
            out.append({
                "owning_brand_id":  brand_id,
                "tag":              tag,
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
    rows.extend(parse_period(pick_period(hist), own.get("name", brand_name), True))

    # Competitors
    comp_ts = d.get("competitorTimeSeriesData", {})
    comp_period = pick_period(comp_ts)
    for comp in comp_period.get("competitors", []):
        metrics = comp.get("metrics", {})
        metrics["timestamps"] = comp_period.get("timestamps", [])
        rows.extend(parse_period(metrics, comp.get("name"), comp.get("isOwnBrand", False)))

    bq_append(client, tbl("L0_tag_table"), rows)


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    today = date.today()

    if BACKFILL_START:
        iso_start = BACKFILL_START
        iso_end   = BACKFILL_END if BACKFILL_END else today.isoformat()
        mode = f"BACKFILL {iso_start} → {iso_end}"
    else:
        iso_start = (today - timedelta(days=7)).isoformat()
        iso_end   = today.isoformat()
        mode = "denní run (posledních 7 dní — zachytí aktuální týdenní snapshot)"

    log.info("╔══════════════════════════════════════════╗")
    log.info(f"║  Rankscale Tag Extract  [{mode}]")
    log.info(f"║  Období: {iso_start} → {iso_end}")
    log.info("╚══════════════════════════════════════════╝")

    client = make_client()
    brands = extract_brands()

    for brand in brands:
        brand_id   = brand["id"]
        brand_name = brand["name"]
        try:
            combinations = fetch_tag_topic_combinations(brand_id)
            for tag, topic_id, topic_name in combinations:
                try:
                    extract_report_by_tag(
                        client, brand_id, brand_name,
                        tag, topic_id, topic_name,
                        iso_start, iso_end,
                    )
                except Exception as e:
                    log.error(f"  Tag '{tag}' / topic '{topic_id}' selhal: {e}")

        except Exception as e:
            log.error(f"Brand {brand_id} selhal: {e}")

    log.info("╔══════════════════════════════════════════╗")
    log.info("║  Hotovo ✓                                 ║")
    log.info("╚══════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
