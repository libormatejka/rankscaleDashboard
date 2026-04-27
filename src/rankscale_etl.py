"""
Rankscale Metrics API → BigQuery ETL
Spouští se denně přes GitHub Actions.
"""

import os
import time
import json
import logging
from datetime import date, datetime, timezone
from typing import Any

import requests
from google.cloud import bigquery
from google.oauth2 import service_account

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Konfigurace (z environment proměnných / GitHub Secrets) ───────────────────
RANKSCALE_API_KEY  = os.environ["RANKSCALE_API_KEY"]      # rk_...
GCP_PROJECT        = os.environ["GCP_PROJECT"]             # libor-matejkacz
BQ_DATASET         = os.environ.get("BQ_DATASET", "RankscaleMetrics")
GCP_CREDENTIALS    = os.environ.get("GCP_SA_JSON")         # JSON string service accountu

BASE_URL           = "https://rankscale.ai"
TIME_FRAME         = "7d"       # kolik dat táhneš při každém runu (překryv = bezpečný MERGE)
AGGREGATION        = "daily"
RATE_LIMIT_SLEEP   = 0.4        # sekund mezi voláními (max 200 req/min = 0.3s, dáme buffer)
TODAY              = date.today().isoformat()
NOW                = datetime.now(timezone.utc).isoformat()


# ── BigQuery klient ────────────────────────────────────────────────────────────
def get_bq_client() -> bigquery.Client:
    if GCP_CREDENTIALS:
        info = json.loads(GCP_CREDENTIALS)
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return bigquery.Client(project=GCP_PROJECT, credentials=creds)
    # Fallback: Application Default Credentials (lokální vývoj)
    return bigquery.Client(project=GCP_PROJECT)


def table(name: str) -> str:
    return f"`{GCP_PROJECT}.{BQ_DATASET}.{name}`"


# ── Rankscale API helper ───────────────────────────────────────────────────────
session = requests.Session()
session.headers.update({
    "Authorization": f"Bearer {RANKSCALE_API_KEY}",
    "Content-Type": "application/json",
})


def api_get(path: str, params: dict = None) -> dict:
    url = f"{BASE_URL}{path}"
    log.info(f"GET {path} {params or ''}")
    r = session.get(url, params=params, timeout=30)
    r.raise_for_status()
    time.sleep(RATE_LIMIT_SLEEP)
    return r.json()


def api_post(path: str, body: dict) -> dict:
    url = f"{BASE_URL}{path}"
    log.info(f"POST {path}")
    r = session.post(url, json=body, timeout=30)
    r.raise_for_status()
    time.sleep(RATE_LIMIT_SLEEP)
    return r.json()


def api_post_paginated(path: str, body: dict, limit: int = 50) -> list:
    """Stránkuje přes offset dokud hasMore = False."""
    all_items = []
    offset = 0
    while True:
        paged_body = {**body, "limit": limit, "offset": offset}
        data = api_post(path, paged_body)
        items = data.get("data", {}).get("citations", [])
        all_items.extend(items)
        pagination = data.get("data", {}).get("pagination", {})
        if not pagination.get("hasMore", False):
            break
        offset += limit
        log.info(f"  → stránkuji, offset={offset}, celkem={len(all_items)}")
    return all_items


# ── Load-job helpers ───────────────────────────────────────────────────────────
# Používáme load jobs místo streaming inserts (insert_rows_json).
# Důvod: streaming insert plní "streaming buffer" – BQ pak neumožňuje
# DELETE ani overwrite dokud se buffer nevyprázdní (hodiny).
# Load jobs zapisují přímo do table storage – žádný streaming buffer.

def _clean_rows(rows: list[dict]) -> list[dict]:
    """Převede dict/list hodnoty na JSON string, přidá loaded_at."""
    result = []
    for row in rows:
        clean = {}
        for col, val in row.items():
            if isinstance(val, (dict, list)):
                clean[col] = json.dumps(val, ensure_ascii=False)
            else:
                clean[col] = val
        clean["loaded_at"] = NOW
        result.append(clean)
    return result


def _load_job(client: bigquery.Client, target_str: str, rows: list[dict],
              write_disposition: str) -> None:
    """Spustí load job – zapíše rows do target tabulky."""
    import io
    target_clean = target_str.replace("`", "")
    table_ref    = bigquery.TableReference.from_string(target_clean)

    job_config = bigquery.LoadJobConfig(
        write_disposition = write_disposition,
        source_format     = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        autodetect        = False,   # tabulka už existuje, schema přebíráme z ní
    )

    # Serializuj jako NDJSON
    ndjson = "\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in rows)
    data   = io.BytesIO(ndjson.encode("utf-8"))

    job = client.load_table_from_file(data, table_ref, job_config=job_config)
    job.result()   # čeká na dokončení
    if job.errors:
        raise RuntimeError(f"Load job chyba v {target_str}: {job.errors}")


def load_truncate(client: bigquery.Client, target: str, rows: list[dict]) -> None:
    """
    WRITE_TRUNCATE – nahradí celý obsah tabulky.
    Vhodné pro dim tabulky (dim_brands, dim_search_terms) které jsou malé
    a každý den je nahrazujeme čerstvými daty z API.
    """
    if not rows:
        log.warning(f"  → žádná data pro {target}, přeskakuji")
        return
    clean = _clean_rows(rows)
    log.info(f"  → TRUNCATE + LOAD do {target} ({len(clean)} řádků)")
    _load_job(client, target, clean, bigquery.WriteDisposition.WRITE_TRUNCATE)
    log.info(f"  ✓ hotov")


def load_partitions(client: bigquery.Client, target: str, rows: list[dict],
                    date_col: str) -> None:
    """
    Overwrite per date partition – přepíše jen dotčené dny, ostatní nechá.
    Vhodné pro fact tabulky partitioned by date.
    Každý jedinečný den v datech = jeden load job s partition decoratorem.
    """
    if not rows:
        log.warning(f"  → žádná data pro {target}, přeskakuji")
        return
    clean = _clean_rows(rows)

    # Roztřiď řádky per datum
    from collections import defaultdict
    by_date: dict[str, list] = defaultdict(list)
    for row in clean:
        day = str(row.get(date_col, TODAY))[:10].replace("-", "")  # YYYYMMDD
        by_date[day].append(row)

    log.info(f"  → PARTITION OVERWRITE do {target} ({len(clean)} řádků, {len(by_date)} partitions)")
    target_clean = target.replace("`", "")
    for day, day_rows in by_date.items():
        partition_target = f"`{target_clean}${day}`"
        _load_job(client, partition_target, day_rows, bigquery.WriteDisposition.WRITE_TRUNCATE)

    log.info(f"  ✓ hotov")


def load_append_dedup(client: bigquery.Client, target: str, rows: list[dict],
                      dedup_key: str) -> None:
    """
    Append pouze nových řádků (dedup podle dedup_key).
    Vhodné pro fact_answer_texts kde execution_id je unikátní navždy.
    """
    if not rows:
        log.warning(f"  → žádná data pro {target}, přeskakuji")
        return

    existing_sql = f"SELECT `{dedup_key}` FROM {target}"
    existing     = {str(row[dedup_key]) for row in client.query(existing_sql).result()}
    new_rows     = [r for r in rows if str(r.get(dedup_key, "")) not in existing]
    log.info(f"  → {len(new_rows)} nových řádků z {len(rows)} celkem")

    if not new_rows:
        log.info(f"  ✓ nic nového")
        return

    clean = _clean_rows(new_rows)
    _load_job(client, target, clean, bigquery.WriteDisposition.WRITE_APPEND)
    log.info(f"  ✓ hotov")


# ══════════════════════════════════════════════════════════════════════════════
# KROKY ETL
# ══════════════════════════════════════════════════════════════════════════════

def step_brands(client: bigquery.Client) -> str:
    """GET /v1/metrics/brands → dim_brands. Vrátí brand_id."""
    log.info("━━ KROK 1: dim_brands")
    data = api_get("/v1/metrics/brands", {"limit": 1000})
    brands = data["data"]["brands"]
    log.info(f"  → {len(brands)} brandů nalezeno")

    rows = [{
        "brand_id":          b["id"],
        "name":              b["name"],
        "domain":            b.get("domain"),
        "variants":          b.get("variants", []),
        "search_term_count": b.get("searchTermCount"),
        "created_at":        b.get("createdAt"),
    } for b in brands]

    load_truncate(client, table("dim_brands"), rows)
    return brands[0]["id"]   # předpokládáme 1 brand


def step_search_terms(client: bigquery.Client, brand_id: str):
    """GET /v1/metrics/search-terms → dim_search_terms."""
    log.info("━━ KROK 2: dim_search_terms")
    data = api_get("/v1/metrics/search-terms", {"brandId": brand_id, "limit": 1000})
    terms = data["data"]["searchTerms"]
    log.info(f"  → {len(terms)} search terms nalezeno")

    rows = [{
        "search_term_id": t["id"],
        "brand_id":       brand_id,
        "query":          t["query"],
        "topic":          t.get("topic"),
        "tags":           t.get("tags", []),
        "engines":        t.get("engines", []),
        "interval":       t.get("interval"),
        "region":         t.get("region"),
        "active":         t.get("active"),
        "created_at":     t.get("createdAt"),
    } for t in terms]

    load_truncate(client, table("dim_search_terms"), rows)


def step_report(client: bigquery.Client, brand_id: str):
    """POST /v1/metrics/report → fact_report_timeseries + fact_report_by_engine."""
    log.info("━━ KROK 3: fact_report_timeseries + fact_report_by_engine")
    data = api_post("/v1/metrics/report", {
        "brandId":       brand_id,
        "timeFrame":     TIME_FRAME,
        "aggregation":   AGGREGATION,
        "periodOffset":  0,
        "selectedTopic": "all",
        "selectedTags":  "all",
        "selectedEngine": "all",
        "selectedQuery": "all",
    })

    # timeSeries → fact_report_timeseries (partition overwrite per den)
    ts_rows = [{
        "date":              row["date"][:10],
        "brand_id":          brand_id,
        "aggregation_level": AGGREGATION,
        "visibility":        row.get("visibility"),
        "position":          row.get("position"),
        "sentiment":         row.get("sentiment"),
        "mentions":          row.get("mentions"),
        "detection_rate":    row.get("detectionRate"),
        "citations":         row.get("citations"),
        "top3_pct":          row.get("top3Pct"),
    } for row in data["data"].get("timeSeries", [])]
    load_partitions(client, table("fact_report_timeseries"), ts_rows, date_col="date")

    # byEngine → fact_report_by_engine (snapshot_date partition overwrite)
    by_engine = data["data"].get("byEngine", {})
    engine_rows = [{
        "snapshot_date": TODAY,
        "brand_id":      brand_id,
        "engine_name":   engine,
        "time_frame":    TIME_FRAME,
        "visibility":    metrics.get("visibility"),
        "position":      metrics.get("position"),
        "mentions":      metrics.get("mentions"),
    } for engine, metrics in by_engine.items()]
    load_partitions(client, table("fact_report_by_engine"), engine_rows, date_col="snapshot_date")


def step_search_term_snapshots(client: bigquery.Client, brand_id: str):
    """POST /v1/metrics/search-terms-report → fact_search_term_snapshots."""
    log.info("━━ KROK 4: fact_search_term_snapshots")
    data = api_post("/v1/metrics/search-terms-report", {
        "brandId":            brand_id,
        "timeFrame":          TIME_FRAME,
        "periodOffset":       0,
        "selectedTopic":      "all",
        "selectedTags":       "all",
        "selectedEngine":     "all",
        "selectedQuery":      "all",
        "includeAnswerTexts": False,
    })

    rows = []
    for t in data["data"].get("searchTerms", []):
        lr    = t.get("latestRun") or {}
        trend = t.get("trend") or {}
        rows.append({
            "snapshot_date":           TODAY,
            "search_term_id":          t["searchTermId"],
            "brand_id":                brand_id,
            "query":                   t.get("query"),
            "topic":                   t.get("topic"),
            "tags":                    t.get("tags", []),
            "latest_run_date":         lr.get("date"),
            "visibility":              lr.get("visibility"),
            "position":                lr.get("position"),
            "sentiment":               lr.get("sentiment"),
            "mentions":                lr.get("mentions"),
            "citations":               lr.get("citations"),
            "engines_detail":          lr.get("engines", {}),
            "trend_visibility_change": (trend.get("visibility") or {}).get("change"),
            "trend_visibility_dir":    (trend.get("visibility") or {}).get("direction"),
            "trend_position_change":   (trend.get("position") or {}).get("change"),
            "trend_position_dir":      (trend.get("position") or {}).get("direction"),
        })

    load_partitions(client, table("fact_search_term_snapshots"), rows, date_col="snapshot_date")


def step_answer_texts(client: bigquery.Client, brand_id: str):
    """POST /v1/metrics/search-terms-report s includeAnswerTexts=true → fact_answer_texts."""
    log.info("━━ KROK 5: fact_answer_texts")
    data = api_post("/v1/metrics/search-terms-report", {
        "brandId":            brand_id,
        "timeFrame":          TIME_FRAME,
        "periodOffset":       0,
        "selectedTopic":      "all",
        "selectedTags":       "all",
        "selectedEngine":     "all",
        "selectedQuery":      "all",
        "includeAnswerTexts": True,
    })

    rows = []
    for t in data["data"].get("searchTerms", []):
        for at in t.get("answerTexts") or []:
            rows.append({
                "execution_id":   at["executionId"],
                "search_term_id": t["searchTermId"],
                "brand_id":       brand_id,
                "query":          t.get("query"),
                "executed_at":    at.get("executedAt"),
                "engine_name":    at.get("engine"),
                "answer_text":    at.get("answerText"),
            })

    log.info(f"  → {len(rows)} answer texts k načtení")
    load_append_dedup(client, table("fact_answer_texts"), rows, dedup_key="execution_id")


def step_sentiment(client: bigquery.Client, brand_id: str):
    """POST /v1/metrics/sentiment → fact_sentiment_timeseries + fact_sentiment_by_engine."""
    log.info("━━ KROK 6: fact_sentiment_timeseries + fact_sentiment_by_engine")
    data = api_post("/v1/metrics/sentiment", {
        "brandId":        brand_id,
        "timeFrame":      TIME_FRAME,
        "periodOffset":   0,
        "selectedTopic":  "all",
        "selectedEngine": "all",
        "selectedQuery":  "all",
    })

    ts_rows = [{
        "date":            row["date"][:10],
        "brand_id":        brand_id,
        "sentiment_score": row.get("score"),
        "positive_pct":    row.get("positive"),
        "neutral_pct":     row.get("neutral"),
        "negative_pct":    row.get("negative"),
    } for row in data["data"].get("timeSeries", [])]
    load_partitions(client, table("fact_sentiment_timeseries"), ts_rows, date_col="date")

    by_engine = data["data"].get("byEngine", {})
    engine_rows = [{
        "snapshot_date":   TODAY,
        "brand_id":        brand_id,
        "engine_name":     engine,
        "sentiment_score": metrics.get("score"),
        "sentiment_label": metrics.get("label"),
    } for engine, metrics in by_engine.items()]
    load_partitions(client, table("fact_sentiment_by_engine"), engine_rows, date_col="snapshot_date")


def step_citations(client: bigquery.Client, brand_id: str):
    """POST /v1/metrics/citations → fact_citations (se stránkováním)."""
    log.info("━━ KROK 7: fact_citations")
    citations = api_post_paginated("/v1/metrics/citations", {
        "brandId":        brand_id,
        "timeFrame":      TIME_FRAME,
        "periodOffset":   0,
        "selectedTopic":  "all",
        "selectedEngine": "all",
        "selectedQuery":  "all",
    })
    log.info(f"  → {len(citations)} citací celkem")

    rows = [{
        "search_term_id": c["searchTermId"],
        "brand_id":       brand_id,
        "engine_name":    c.get("engine"),
        "url":            c.get("url"),
        "title":          c.get("title"),
        "domain":         c.get("domain"),
        "query":          c.get("query"),
        "first_seen":     c.get("firstSeen"),
        "last_seen":      c.get("lastSeen"),
        "citation_count": c.get("count"),
    } for c in citations]

    # Citations: overwrite last_seen partition (API aktualizuje count průběžně)
    load_partitions(client, table("fact_citations"), rows, date_col="last_seen")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("╔══════════════════════════════════════════════╗")
    log.info("║  Rankscale ETL start  –  " + TODAY + "       ║")
    log.info("╚══════════════════════════════════════════════╝")

    client = get_bq_client()

    brand_id = step_brands(client)
    log.info(f"  → brand_id: {brand_id}")

    step_search_terms(client, brand_id)
    step_report(client, brand_id)
    step_search_term_snapshots(client, brand_id)
    step_answer_texts(client, brand_id)
    step_sentiment(client, brand_id)
    step_citations(client, brand_id)

    log.info("╔══════════════════════════════════════════════╗")
    log.info("║  ETL dokončen úspěšně  ✓                     ║")
    log.info("╚══════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
