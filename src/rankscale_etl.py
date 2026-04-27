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


# ── MERGE helper ──────────────────────────────────────────────────────────────
def merge(client: bigquery.Client, target: str, rows: list[dict], merge_keys: list[str], job_config=None):
    if not rows:
        log.warning(f"  → žádná data pro {target}, přeskakuji")
        return

    # Vytvoř dočasnou tabulku
    temp_table = f"{target}_tmp_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    temp_table_clean = temp_table.replace("`", "")

    # Inferuj schema z prvního řádku
    sample = rows[0]
    schema = []
    for col, val in sample.items():
        if isinstance(val, bool):
            field_type = "BOOL"
        elif isinstance(val, int):
            field_type = "INT64"
        elif isinstance(val, float):
            field_type = "FLOAT64"
        elif isinstance(val, (dict, list)):
            field_type = "JSON"
        else:
            field_type = "STRING"
        schema.append(bigquery.SchemaField(col, field_type))

    # Přetypuj hodnoty
    clean_rows = []
    for row in rows:
        clean = {}
        for col, val in row.items():
            if isinstance(val, (dict, list)):
                clean[col] = json.dumps(val, ensure_ascii=False)
            else:
                clean[col] = val
        clean_rows.append(clean)

    # Nahraj do temp tabulky
    temp_ref = bigquery.TableReference.from_string(temp_table_clean)
    temp_obj = bigquery.Table(temp_ref, schema=schema)
    temp_obj = client.create_table(temp_obj, exists_ok=True)
    errors = client.insert_rows_json(temp_obj, clean_rows)
    if errors:
        raise RuntimeError(f"Chyba při nahrávání do temp tabulky: {errors}")

    # Sestav MERGE SQL
    all_cols     = list(sample.keys())
    update_cols  = [c for c in all_cols if c not in merge_keys and c != "loaded_at"]
    on_clause    = " AND ".join([f"T.{k} = S.{k}" for k in merge_keys])
    update_set   = ", ".join([f"T.{c} = S.{c}" for c in update_cols])
    update_set  += ", T.loaded_at = CURRENT_TIMESTAMP()"
    insert_cols  = ", ".join(all_cols)
    insert_vals  = ", ".join([f"S.{c}" for c in all_cols])

    merge_sql = f"""
    MERGE {target} T
    USING `{temp_table_clean}` S
    ON {on_clause}
    WHEN MATCHED THEN
      UPDATE SET {update_set}
    WHEN NOT MATCHED THEN
      INSERT ({insert_cols}, loaded_at)
      VALUES ({insert_vals}, CURRENT_TIMESTAMP())
    """

    log.info(f"  → MERGE do {target} ({len(rows)} řádků)")
    client.query(merge_sql).result()
    client.delete_table(temp_table_clean, not_found_ok=True)
    log.info(f"  ✓ MERGE hotov")


def insert_new_only(client: bigquery.Client, target: str, rows: list[dict], dedup_key: str):
    """INSERT pouze řádků které ještě neexistují (podle dedup_key)."""
    if not rows:
        log.warning(f"  → žádná data pro {target}, přeskakuji")
        return

    # Načti existující klíče
    existing_sql = f"SELECT {dedup_key} FROM {target}"
    existing = {row[dedup_key] for row in client.query(existing_sql).result()}
    new_rows = [r for r in rows if r.get(dedup_key) not in existing]
    log.info(f"  → {len(new_rows)} nových řádků (z {len(rows)} celkem)")

    if not new_rows:
        return

    clean_rows = []
    for row in new_rows:
        clean = {}
        for col, val in row.items():
            clean[col] = json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else val
        clean["loaded_at"] = NOW
        clean_rows.append(clean)

    target_clean = target.replace("`", "")
    errors = client.insert_rows_json(target_clean, clean_rows)
    if errors:
        raise RuntimeError(f"Chyba při INSERT: {errors}")
    log.info(f"  ✓ INSERT {len(clean_rows)} nových řádků")


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

    merge(client, table("dim_brands"), rows, merge_keys=["brand_id"])
    return brands[0]["id"]   # předpokládáme 1 brand


def step_search_terms(client: bigquery.Client, brand_id: str):
    """GET /v1/metrics/search-terms → dim_search_terms."""
    log.info("━━ KROK 2: dim_search_terms")
    data = api_get("/v1/metrics/search-terms", {"brandId": brand_id, "limit": 1000})
    terms = data["data"]["searchTerms"]
    log.info(f"  → {len(terms)} search terms nalezeno")

    rows = [{
        "search_term_id": t["id"],
        "brand_id":       t["brandId"],
        "query":          t["query"],
        "topic":          t.get("topic"),
        "tags":           t.get("tags", []),
        "engines":        t.get("engines", []),
        "interval":       t.get("interval"),
        "region":         t.get("region"),
        "active":         t.get("active"),
        "created_at":     t.get("createdAt"),
    } for t in terms]

    merge(client, table("dim_search_terms"), rows, merge_keys=["search_term_id"])


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

    # timeSeries → fact_report_timeseries
    ts_rows = [{
        "date":              row["date"][:10],   # ISO date string
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
    merge(client, table("fact_report_timeseries"), ts_rows,
          merge_keys=["date", "brand_id", "aggregation_level"])

    # byEngine → fact_report_by_engine
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
    merge(client, table("fact_report_by_engine"), engine_rows,
          merge_keys=["snapshot_date", "brand_id", "engine_name"])


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
        lr = t.get("latestRun") or {}
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

    merge(client, table("fact_search_term_snapshots"), rows,
          merge_keys=["snapshot_date", "search_term_id"])


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
    insert_new_only(client, table("fact_answer_texts"), rows, dedup_key="execution_id")


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

    # timeSeries → fact_sentiment_timeseries
    ts_rows = [{
        "date":            row["date"][:10],
        "brand_id":        brand_id,
        "sentiment_score": row.get("score"),
        "positive_pct":    row.get("positive"),
        "neutral_pct":     row.get("neutral"),
        "negative_pct":    row.get("negative"),
    } for row in data["data"].get("timeSeries", [])]
    merge(client, table("fact_sentiment_timeseries"), ts_rows,
          merge_keys=["date", "brand_id"])

    # byEngine → fact_sentiment_by_engine
    by_engine = data["data"].get("byEngine", {})
    engine_rows = [{
        "snapshot_date":   TODAY,
        "brand_id":        brand_id,
        "engine_name":     engine,
        "sentiment_score": metrics.get("score"),
        "sentiment_label": metrics.get("label"),
    } for engine, metrics in by_engine.items()]
    merge(client, table("fact_sentiment_by_engine"), engine_rows,
          merge_keys=["snapshot_date", "brand_id", "engine_name"])


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

    merge(client, table("fact_citations"), rows,
          merge_keys=["search_term_id", "engine_name", "url"])


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
