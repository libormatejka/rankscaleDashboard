"""
Rankscale → BigQuery  |  Raw Extract  (L0 vrstva)
Stahuje data z Rankscale API a ukládá je 1:1 do BigQuery (raw_ tabulky).
Žádná transformační logika — ta patří do transformačních SQL skriptů.

Režimy spuštění:
  - Denní run (výchozí): stáhne aktuální týden, přeskočí pokud nejsou nová data
  - Backfill:            BACKFILL_WEEKS=N projde N týdnů zpět (vždy zapíše)
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
API_BASE       = "https://rankscale.ai"
API_KEY        = os.environ["RANKSCALE_API_KEY"]
GCP_PROJECT    = os.environ["GCP_PROJECT"]
BQ_DATASET     = os.environ["BQ_DATASET"]
BACKFILL_WEEKS = int(os.environ["BACKFILL_WEEKS"]) if os.environ.get("BACKFILL_WEEKS") else None
RATE_SLEEP     = 0.5

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


def bq_max_snapshot(client: bigquery.Client, brand_id: str) -> datetime | None:
    """Vrátí MAX(last_snapshot_at) z raw_brand_snapshots pro daný brand. None pokud tabulka prázdná."""
    query = f"""
        SELECT MAX(last_snapshot_at) AS max_snap
        FROM `{GCP_PROJECT}.{BQ_DATASET}.raw_brand_snapshots`
        WHERE brand_id = '{brand_id}'
    """
    try:
        rows = list(client.query(query).result())
        return rows[0].max_snap if rows and rows[0].max_snap else None
    except Exception:
        return None


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
                "created_at":           t.get("createdAt"),
                "last_execution_time":  t.get("lastExecutionTime"),
                "next_execution_time":  t.get("nextScheduledExecutionTime"),
                "executions_amount":    t.get("executionsAmount"),
            })
        bq_append(client, tbl("search_terms"), rows)
        log.info(f"    {brand_id}: {len(rows)} termů")
        time.sleep(RATE_SLEEP)


def _fetch_snapshots(brand_id: str, period_offset: int) -> tuple[list[dict], datetime | None]:
    """
    Zavolá search-terms-report API a vrátí (rows, api_max_snapshot_at).
    rows = připravené řádky pro raw_brand_snapshots.
    api_max_snapshot_at = nejnovější lastSnapshotAt ze všech search termů v response.
    """
    data  = api_post("/v1/metrics/search-terms-report", {
        "brandId":            brand_id,
        "timeFrame":          "7d",
        "periodOffset":       period_offset,
        "selectedTopic":      "all",
        "selectedTags":       "all",
        "selectedEngine":     "all",
        "selectedQuery":      "all",
        "includeAnswerTexts": False,
    })
    terms = data["data"].get("searchTerms", [])
    rows  = []
    max_snap = None

    for t in terms:
        topic  = t.get("topic") or {}
        engine = (t.get("aiSearchEngines") or [""])[0]
        snap   = t.get("lastSnapshotAt")

        if snap:
            snap_dt = datetime.fromisoformat(snap.replace("Z", "+00:00"))
            if max_snap is None or snap_dt > max_snap:
                max_snap = snap_dt

        base = {
            "brand_id":         brand_id,
            "search_term_id":   t["searchTermId"],
            "engine":           engine,
            "topic_id":         topic.get("id"),
            "topic_name":       topic.get("name"),
            "last_snapshot_at": snap,
        }

        def make_row(b: dict, is_own: bool) -> dict:
            return {
                **base,
                "brand_name":       b.get("name"),
                "is_own_brand":     is_own,
                "visibility_score": b.get("visibilityScore"),
                "avg_sentiment":    b.get("avgSentiment"),
                "avg_rank":         b.get("avgRank"),
                "latest_rank":      b.get("latestRank"),
                "detection_rate":   b.get("detectionRate"),
                "top3_rate":        b.get("top3"),
                "citation_count":   b.get("citationCount"),
                "appearances":      b.get("appearances"),
            }

        if "ownBrand" in t:
            rows.append(make_row(t["ownBrand"], is_own=True))
        for comp in t.get("competitors", []):
            rows.append(make_row(comp, is_own=False))

    return rows, max_snap


def _fetch_answer_texts(brand_id: str, period_offset: int) -> list[dict]:
    data  = api_post("/v1/metrics/search-terms-report", {
        "brandId":            brand_id,
        "timeFrame":          "7d",
        "periodOffset":       period_offset,
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
    return rows


def extract_snapshots_and_texts(
    client: bigquery.Client,
    brand_id: str,
    period_offset: int,
    force: bool = False,
) -> bool:
    """
    Stáhne brand_snapshots a answer_texts pro daný brand a offset.
    force=True: vždy zapíše (backfill).
    force=False: přeskočí pokud BQ už má data pro tento snapshot (denní run).
    Vrátí True pokud data byla zapsána, False pokud přeskočeno.
    """
    log.info(f"── brand_snapshots + answer_texts  (brand={brand_id}, offset={period_offset})")

    snap_rows, api_max = _fetch_snapshots(brand_id, period_offset)

    if not force and period_offset == 0:
        bq_max = bq_max_snapshot(client, brand_id)
        if api_max and bq_max and api_max <= bq_max:
            log.info(f"    → přeskočeno: BQ již má snapshot {api_max.date()} (žádná nová data)")
            return False

    bq_append(client, tbl("brand_snapshots"), snap_rows)
    time.sleep(RATE_SLEEP)

    text_rows = _fetch_answer_texts(brand_id, period_offset)
    bq_append(client, tbl("answer_texts"), text_rows)

    return True


def extract_citations(client: bigquery.Client, brand_id: str) -> None:
    log.info(f"── citations  (brand={brand_id})")
    data = api_post("/v1/metrics/citations", {
        "brandId":   brand_id,
        "timeFrame": "7d",
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


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    mode = f"BACKFILL {BACKFILL_WEEKS} týdnů" if BACKFILL_WEEKS else "denní run"
    log.info("╔══════════════════════════════════════════╗")
    log.info(f"║  Rankscale Raw Extract  [{mode}]")
    log.info("╚══════════════════════════════════════════╝")

    client    = make_client()
    brand_ids = extract_brands(client)
    extract_search_terms(client, brand_ids)

    # Backfill: offset N-1 → 0 (od nejstaršího po nejnovější)
    # Denní run: jen offset 0
    offsets = list(range(BACKFILL_WEEKS - 1, -1, -1)) if BACKFILL_WEEKS else [0]
    is_backfill = bool(BACKFILL_WEEKS)

    for brand_id in brand_ids:
        log.info(f"━━ Brand: {brand_id}")
        try:
            for offset in offsets:
                written = extract_snapshots_and_texts(
                    client, brand_id, offset, force=is_backfill
                )
                time.sleep(RATE_SLEEP)

            # Citations: vždy jen aktuální týden (nemají vlastní timestamp pro historii)
            extract_citations(client, brand_id)
            time.sleep(RATE_SLEEP)

        except Exception as e:
            log.error(f"Brand {brand_id} selhal: {e}")

    log.info("╔══════════════════════════════════════════╗")
    log.info("║  Hotovo ✓                                 ║")
    log.info("╚══════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
