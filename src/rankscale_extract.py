"""
Rankscale → BigQuery  |  Raw Extract
Stahuje data z Rankscale API a ukládá je 1:1 do BigQuery (raw_ tabulky).
Žádná transformační logika — ta patří do Kebooly.
"""

import io
import json
import logging
import os
import time
from datetime import datetime, timezone

import requests
from google.cloud import bigquery
from google.oauth2 import service_account

# ── Konfigurace ────────────────────────────────────────────────────────────────
API_BASE    = "https://rankscale.ai"
API_KEY     = os.environ["RANKSCALE_API_KEY"]
GCP_PROJECT = os.environ["GCP_PROJECT"]
BQ_DATASET  = os.environ["BQ_DATASET"]
TIME_FRAME  = os.environ.get("TIME_FRAME", "7d")
RATE_SLEEP  = 0.5

NOW = datetime.now(timezone.utc).isoformat()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ── BigQuery ───────────────────────────────────────────────────────────────────
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
        log.info(f"  → raw_{table.split('.')[-1]}: 0 řádků, přeskakuji")
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
    log.info(f"  → {table.split('.')[-1]}: {len(rows)} řádků")


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


# ── Extract kroky ──────────────────────────────────────────────────────────────
def extract_brands(client: bigquery.Client) -> list[str]:
    log.info("── brands")
    data   = api_get("/v1/metrics/brands", {"limit": 1000})
    brands = data["data"]["brands"]
    rows   = [
        {
            "brand_id":     b["id"],
            "name":         b["name"],
            "domain":       b.get("url"),
            "is_own_brand": True,
        }
        for b in brands
    ]
    bq_append(client, tbl("brands"), rows)
    ids = [b["id"] for b in brands]
    log.info(f"    {len(ids)} brand(ů): {ids}")
    return ids


def extract_search_terms(client: bigquery.Client, brand_ids: list[str]) -> None:
    log.info("── search_terms")
    for brand_id in brand_ids:
        data  = api_get("/v1/metrics/search-terms", {"brandId": brand_id, "limit": 5000})
        terms = data["data"]["searchTerms"]
        rows  = []
        for t in terms:
            topic = t.get("searchTermTopicRef") or {}
            rows.append({
                "brand_id":             brand_id,
                "search_term_id":       t["id"],
                "query":                t.get("term"),
                "engine":               (t.get("aiSearchEngines") or [""])[0],
                "topic_id":             topic.get("id"),
                "topic_name":           topic.get("name"),
                "region":               t.get("region"),
                "interval":             t.get("interval"),
                "tags":                 json.dumps(t.get("tags", []), ensure_ascii=False),
                "status":               t.get("status"),
                "last_execution_time":  t.get("lastExecutionTime"),
                "next_execution_time":  t.get("nextScheduledExecutionTime"),
                "executions_amount":    t.get("executionsAmount"),
            })
        bq_append(client, tbl("search_terms"), rows)
        log.info(f"    {brand_id}: {len(rows)} termů")
        time.sleep(RATE_SLEEP)


def extract_brand_snapshots(client: bigquery.Client, brand_id: str) -> None:
    log.info(f"── brand_snapshots  ({brand_id})")
    data  = api_post("/v1/metrics/search-terms-report", {
        "brandId":            brand_id,
        "timeFrame":          TIME_FRAME,
        "selectedTopic":      "all",
        "selectedTags":       "all",
        "selectedEngine":     "all",
        "selectedQuery":      "all",
        "includeAnswerTexts": False,
    })
    terms = data["data"].get("searchTerms", [])
    rows  = []

    for t in terms:
        topic  = t.get("topic") or {}
        engine = (t.get("aiSearchEngines") or [""])[0]
        base   = {
            "brand_id":         brand_id,
            "search_term_id":   t["searchTermId"],
            "engine":           engine,
            "topic_id":         topic.get("id"),
            "topic_name":       topic.get("name"),
            "last_snapshot_at": t.get("lastSnapshotAt"),
        }

        def make_brand_row(b: dict, is_own: bool) -> dict:
            return {
                **base,
                "brand_name":      b.get("name"),
                "is_own_brand":    is_own,
                "visibility_score": b.get("visibilityScore"),
                "avg_sentiment":   b.get("avgSentiment"),
                "avg_rank":        b.get("avgRank"),
                "latest_rank":     b.get("latestRank"),
                "detection_rate":  b.get("detectionRate"),
                "top3_rate":       b.get("top3"),
                "citation_count":  b.get("citationCount"),
                "appearances":     b.get("appearances"),
            }

        if "ownBrand" in t:
            rows.append(make_brand_row(t["ownBrand"], is_own=True))
        for comp in t.get("competitors", []):
            rows.append(make_brand_row(comp, is_own=False))

    bq_append(client, tbl("brand_snapshots"), rows)
    log.info(f"    {len(rows)} řádků (vlastní brand + competitors)")


def extract_answer_texts(client: bigquery.Client, brand_id: str) -> None:
    log.info(f"── answer_texts  ({brand_id})")
    data  = api_post("/v1/metrics/search-terms-report", {
        "brandId":            brand_id,
        "timeFrame":          TIME_FRAME,
        "selectedTopic":      "all",
        "selectedTags":       "all",
        "selectedEngine":     "all",
        "selectedQuery":      "all",
        "includeAnswerTexts": True,
    })
    terms = data["data"].get("searchTerms", [])
    rows  = []
    for t in terms:
        for at in t.get("answerTexts") or []:
            rows.append({
                "brand_id":       brand_id,
                "search_term_id": t["searchTermId"],
                "execution_id":   at["executionId"],
                "executed_at":    at.get("executedAt"),
                "engine":         at.get("engine"),
                "answer_text":    at.get("answerText"),
            })
    bq_append(client, tbl("answer_texts"), rows)
    log.info(f"    {len(rows)} textů")


def extract_citations(client: bigquery.Client, brand_id: str) -> None:
    log.info(f"── citations  ({brand_id})")
    data = api_post("/v1/metrics/citations", {
        "brandId":   brand_id,
        "timeFrame": TIME_FRAME,
    })
    rows = []
    for term_entry in data["data"].get("domainSummary", {}).get("topDomainsByQuery", []):
        query          = term_entry.get("query", "")
        search_term_id = (term_entry.get("searchTermIds") or [None])[0]
        for engine_entry in term_entry.get("engines", []):
            engine = engine_entry.get("engineId", "")
            for domain_entry in engine_entry.get("domains", []):
                domain      = domain_entry.get("domain", "")
                occurrences = domain_entry.get("occurrences", 0)
                urls        = domain_entry.get("urls") or []
                if urls:
                    for url_entry in urls:
                        rows.append({
                            "brand_id":       brand_id,
                            "search_term_id": search_term_id,
                            "query":          query,
                            "engine":         engine,
                            "domain":         domain,
                            "url":            url_entry.get("url"),
                            "occurrences":    url_entry.get("occurrences", 0),
                        })
                else:
                    rows.append({
                        "brand_id":       brand_id,
                        "search_term_id": search_term_id,
                        "query":          query,
                        "engine":         engine,
                        "domain":         domain,
                        "url":            None,
                        "occurrences":    occurrences,
                    })
    bq_append(client, tbl("citations"), rows)
    log.info(f"    {len(rows)} citací")


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    log.info("╔══════════════════════════════════════╗")
    log.info(f"║  Rankscale Raw Extract  TIME_FRAME={TIME_FRAME}  ║")
    log.info("╚══════════════════════════════════════╝")

    client    = make_client()
    brand_ids = extract_brands(client)
    extract_search_terms(client, brand_ids)

    for brand_id in brand_ids:
        log.info(f"━━ Brand: {brand_id}")
        try:
            extract_brand_snapshots(client, brand_id)
            time.sleep(RATE_SLEEP)
            extract_answer_texts(client, brand_id)
            time.sleep(RATE_SLEEP)
            extract_citations(client, brand_id)
            time.sleep(RATE_SLEEP)
        except Exception as e:
            log.error(f"Brand {brand_id} selhal: {e}")

    log.info("╔══════════════════════════════════════╗")
    log.info("║  Hotovo ✓                             ║")
    log.info("╚══════════════════════════════════════╝")


if __name__ == "__main__":
    main()
