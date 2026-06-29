"""
Rankscale Metrics API → BigQuery ETL
Spouští se denně přes GitHub Actions.

Tabulky (target):
  dim_brands            – číselník brandů (WRITE_TRUNCATE)
  dim_search_terms      – číselník search termů (WRITE_TRUNCATE)
  fact_brand_snapshots  – metriky per brand per search term per týden (PARTITION OVERWRITE)
  fact_answer_texts     – raw AI odpovědi (APPEND + dedup)
"""

import io
import json
import logging
import os
import time
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Optional

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


# ── Konfigurace ────────────────────────────────────────────────────────────────
RANKSCALE_API_KEY = os.environ["RANKSCALE_API_KEY"]
GCP_PROJECT       = os.environ["GCP_PROJECT"]
BQ_DATASET        = os.environ.get("BQ_DATASET", "RankScaleDashboard")
GCP_SA_JSON       = os.environ.get("GCP_SA_JSON")

BASE_URL          = "https://rankscale.ai"
TIME_FRAME        = os.environ.get("TIME_FRAME", "7d")
RATE_LIMIT_SLEEP  = 0.5   # sec mezi voláními (buffer nad limit 200 req/min)

TODAY = date.today().isoformat()
NOW   = datetime.now(timezone.utc).isoformat()


# ── BigQuery ───────────────────────────────────────────────────────────────────
def get_bq_client() -> bigquery.Client:
    if GCP_SA_JSON:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(GCP_SA_JSON),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return bigquery.Client(project=GCP_PROJECT, credentials=creds)
    return bigquery.Client(project=GCP_PROJECT)   # Application Default Credentials


def tbl(name: str) -> str:
    """Vrátí plně kvalifikovaný název tabulky."""
    return f"`{GCP_PROJECT}.{BQ_DATASET}.{name}`"


# ── Rankscale API ──────────────────────────────────────────────────────────────
_session = requests.Session()
_session.headers.update({
    "Authorization": f"Bearer {RANKSCALE_API_KEY}",
    "Content-Type": "application/json",
})


def api_get(path: str, params: dict = None) -> dict:
    log.info(f"  GET {path}  params={params or {}}")
    r = _session.get(f"{BASE_URL}{path}", params=params, timeout=120)
    r.raise_for_status()
    time.sleep(RATE_LIMIT_SLEEP)
    return r.json()


def api_post(path: str, body: dict) -> dict:
    log.info(f"  POST {path}")
    r = _session.post(f"{BASE_URL}{path}", json=body, timeout=120)
    r.raise_for_status()
    time.sleep(RATE_LIMIT_SLEEP)
    return r.json()


# ── Explicitní schémata fact tabulek ──────────────────────────────────────────
# Potřebujeme je pro `ensure_fact_table` – tabulka se vytvoří automaticky
# pokud neexistuje (např. po DROP nebo při prvním nasazení).

FACT_BRAND_SNAPSHOTS_SCHEMA = [
    bigquery.SchemaField("snapshot_date",   "DATE",      mode="REQUIRED"),
    bigquery.SchemaField("snapshot_week",   "STRING",    mode="REQUIRED"),
    bigquery.SchemaField("search_term_id",  "STRING",    mode="REQUIRED"),
    bigquery.SchemaField("brand_name",      "STRING",    mode="REQUIRED"),
    bigquery.SchemaField("is_own_brand",    "BOOL",      mode="REQUIRED"),
    bigquery.SchemaField("brand_id",        "STRING"),
    bigquery.SchemaField("visibility_score","FLOAT64"),
    bigquery.SchemaField("avg_sentiment",   "FLOAT64"),
    bigquery.SchemaField("avg_rank",        "FLOAT64"),
    bigquery.SchemaField("latest_rank",     "INT64"),
    bigquery.SchemaField("detection_rate",  "FLOAT64"),
    bigquery.SchemaField("top3_rate",       "FLOAT64"),
    bigquery.SchemaField("citation_count",  "INT64"),
    bigquery.SchemaField("appearances",     "INT64"),
    bigquery.SchemaField("engine",          "STRING"),
    bigquery.SchemaField("topic_id",        "STRING"),
    bigquery.SchemaField("last_snapshot_at","TIMESTAMP"),
    bigquery.SchemaField("loaded_at",       "TIMESTAMP"),
]

FACT_CITATIONS_SCHEMA = [
    bigquery.SchemaField("snapshot_date",  "DATE",      mode="REQUIRED"),
    bigquery.SchemaField("snapshot_week",  "STRING",    mode="REQUIRED"),
    bigquery.SchemaField("brand_id",       "STRING",    mode="REQUIRED"),
    bigquery.SchemaField("search_term_id", "STRING"),
    bigquery.SchemaField("engine",         "STRING",    mode="REQUIRED"),
    bigquery.SchemaField("domain",         "STRING",    mode="REQUIRED"),
    bigquery.SchemaField("url",            "STRING"),
    bigquery.SchemaField("occurrences",    "INT64",     mode="REQUIRED"),
    bigquery.SchemaField("loaded_at",      "TIMESTAMP"),
]

FACT_ANSWER_TEXTS_SCHEMA = [
    bigquery.SchemaField("execution_id",   "STRING",    mode="REQUIRED"),
    bigquery.SchemaField("search_term_id", "STRING",    mode="REQUIRED"),
    bigquery.SchemaField("executed_at",    "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("engine",         "STRING"),
    bigquery.SchemaField("answer_text",    "STRING"),
    bigquery.SchemaField("loaded_at",      "TIMESTAMP"),
]


def ensure_fact_table(client: bigquery.Client, target: str,
                      schema: list, partition_field: str,
                      cluster_fields: list[str] = None) -> None:
    """Vytvoří partitioned fact tabulku pokud neexistuje. Idempotentní."""
    raw = target.replace("`", "")
    table_ref = bigquery.TableReference.from_string(raw)
    table = bigquery.Table(table_ref, schema=schema)
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field=partition_field,
    )
    if cluster_fields:
        table.clustering_fields = cluster_fields
    try:
        client.create_table(table)
        log.info(f"    Tabulka {target} vytvořena (neexistovala)")
    except Exception:
        pass  # již existuje


# ── BQ load helpers ────────────────────────────────────────────────────────────
def _prepare(rows: list[dict]) -> list[dict]:
    """Převede dict/list hodnoty na JSON string, přidá loaded_at."""
    out = []
    for row in rows:
        clean = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                 for k, v in row.items()}
        clean["loaded_at"] = NOW
        out.append(clean)
    return out


def _load(client: bigquery.Client, target: str, rows: list[dict],
          disposition: str, autodetect: bool = False) -> None:
    target_ref = bigquery.TableReference.from_string(target.replace("`", ""))
    cfg = bigquery.LoadJobConfig(
        write_disposition=disposition,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        autodetect=autodetect,
    )
    ndjson = "\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in rows)
    job = client.load_table_from_file(io.BytesIO(ndjson.encode()), target_ref, job_config=cfg)
    job.result()
    if job.errors:
        raise RuntimeError(f"BQ load chyba ({target}): {job.errors}")


def bq_truncate(client: bigquery.Client, target: str, rows: list[dict]) -> None:
    """Nahradí celý obsah tabulky. Vhodné pro dim tabulky.
    autodetect=True: schema se odvozuje z dat, takže DDL v BQ nemusí být přesné."""
    if not rows:
        log.warning(f"    žádná data pro {target}, přeskakuji")
        return
    prepared = _prepare(rows)
    log.info(f"    TRUNCATE → {target} ({len(prepared)} řádků)")
    _load(client, target, prepared, bigquery.WriteDisposition.WRITE_TRUNCATE, autodetect=True)


def bq_partition_overwrite(client: bigquery.Client, target: str, rows: list[dict],
                           date_col: str) -> None:
    """Přepíše jen dotčené date partitions. Vhodné pro fact tabulky."""
    if not rows:
        log.warning(f"    žádná data pro {target}, přeskakuji")
        return
    prepared = _prepare(rows)

    by_day: dict[str, list] = defaultdict(list)
    for row in prepared:
        day = str(row.get(date_col, TODAY))[:10].replace("-", "")   # YYYYMMDD
        by_day[day].append(row)

    log.info(f"    PARTITION OVERWRITE → {target} ({len(prepared)} řádků, {len(by_day)} partitions)")
    raw = target.replace("`", "")
    for day, day_rows in by_day.items():
        _load(client, f"`{raw}${day}`", day_rows, bigquery.WriteDisposition.WRITE_TRUNCATE)


def bq_upsert(client: bigquery.Client, target: str, rows: list[dict],
              key_col: str, source_filter: Optional[str] = None) -> None:
    """
    UPSERT přes staging tabulku + MERGE DML.
    - Matched rows    → UPDATE všech sloupců
    - New rows        → INSERT
    - Chybějící rows  → is_active = FALSE (označení jako smazané v Rankscale)
    """
    if not rows:
        log.warning(f"    žádná data pro {target}, přeskakuji")
        return

    prepared = _prepare(rows)

    # Deduplikace podle key_col — MERGE vyžaduje unikátní klíče ve zdroji
    seen: dict = {}
    for row in prepared:
        seen[row[key_col]] = row
    prepared = list(seen.values())

    raw_target  = target.replace("`", "")
    raw_staging = raw_target + "_staging"
    staging_tbl = f"`{raw_staging}`"

    log.info(f"    UPSERT → {target} ({len(prepared)} řádků)")
    _load(client, staging_tbl, prepared, bigquery.WriteDisposition.WRITE_TRUNCATE, autodetect=True)

    columns     = list(prepared[0].keys())
    update_set  = ", ".join(f"T.`{c}` = S.`{c}`" for c in columns if c != key_col)
    insert_cols = ", ".join(f"`{c}`" for c in columns)
    insert_vals = ", ".join(f"S.`{c}`" for c in columns)

    merge_sql = f"""
    MERGE {target} AS T
    USING {staging_tbl} AS S
    ON T.`{key_col}` = S.`{key_col}`
    WHEN MATCHED THEN
      UPDATE SET {update_set}
    WHEN NOT MATCHED BY TARGET THEN
      INSERT ({insert_cols}) VALUES ({insert_vals})
    WHEN NOT MATCHED BY SOURCE {"AND " + source_filter if source_filter else ""} THEN
      UPDATE SET T.`is_active` = FALSE, T.`loaded_at` = CURRENT_TIMESTAMP()
    """
    client.query(merge_sql).result()
    log.info(f"    MERGE dokončen")


def bq_append_dedup(client: bigquery.Client, target: str, rows: list[dict],
                    dedup_col: str) -> None:
    """Přidá pouze řádky jejichž dedup_col ještě není v tabulce."""
    if not rows:
        log.warning(f"    žádná data pro {target}, přeskakuji")
        return

    existing_ids = {
        str(r[dedup_col])
        for r in client.query(f"SELECT `{dedup_col}` FROM {target}").result()
    }
    new_rows = [r for r in rows if str(r.get(dedup_col, "")) not in existing_ids]
    log.info(f"    APPEND DEDUP → {target}: {len(new_rows)} nových z {len(rows)} celkem")

    if not new_rows:
        return
    prepared = _prepare(new_rows)
    _load(client, target, prepared, bigquery.WriteDisposition.WRITE_APPEND)


# ── Pomocné funkce ─────────────────────────────────────────────────────────────
def snapshot_date_from(ts: Optional[str]) -> str:
    """Vrátí DATE z ISO timestamp string, nebo dnešní datum."""
    if ts:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    return TODAY


def iso_week(ts: Optional[str]) -> str:
    """Vrátí ISO week string 'YYYY-WW' z timestamp."""
    d_str = snapshot_date_from(ts)
    d = date.fromisoformat(d_str)
    year, week, _ = d.isocalendar()
    return f"{year}-{week:02d}"


# ══════════════════════════════════════════════════════════════════════════════
# ETL KROKY
# ══════════════════════════════════════════════════════════════════════════════

def has_new_snapshots(client: bigquery.Client, terms: list[dict]) -> bool:
    """
    Porovná nejnovější Rankscale snapshot s posledním záznamem v BQ.
    Vrátí True jen pokud jsou opravdu nová data → ušetří 2 API cally/den.
    """
    # Nejnovější execution z Rankscale (z již stažených search-terms, bez extra API callu)
    api_latest_str = max(
        (t.get("lastExecutionTime") for t in terms if t.get("lastExecutionTime")),
        default=None,
    )
    if not api_latest_str:
        return True  # fallback: nevíme, raději stáhni

    api_latest = datetime.fromisoformat(api_latest_str.replace("Z", "+00:00"))

    # Nejnovější snapshot v BQ (prázdná tabulka = None)
    try:
        result = list(client.query(
            f"SELECT MAX(last_snapshot_at) AS latest FROM {tbl('brand_snapshots')}"
        ).result())
        bq_latest = result[0]["latest"] if result else None
    except Exception:
        return True  # tabulka neexistuje nebo prázdná → stahuj

    if bq_latest is None:
        return True

    # Přidej timezone info pokud chybí (BQ vrací naive datetime)
    if bq_latest.tzinfo is None:
        bq_latest = bq_latest.replace(tzinfo=timezone.utc)

    fresh = api_latest > bq_latest
    if not fresh:
        log.info(f"    Žádná nová data (BQ={bq_latest.date()}, API={api_latest.date()}) – přeskakuji kroky 3+4+5")
    else:
        log.info(f"    Nová data detekována ({api_latest.date()}), spouštím stahování")
    return fresh


def step_brands(client: bigquery.Client) -> list[str]:
    """
    GET /v1/metrics/brands → dim_brands
    Vrátí seznam brand_id všech brandů ve workspace.
    """
    log.info("━━ KROK 1: brands")
    data   = api_get("/v1/metrics/brands")
    brands = data["data"]["brands"]
    log.info(f"    {len(brands)} brand(ů) nalezeno")

    rows = []
    for b in brands:
        rows.append({
            "brand_id":          b["id"],
            "name":              b["name"],
            "domain":            b.get("url"),                          # reálný klíč je "url"
            "is_own_brand":      True,                                  # brands endpoint vrací jen vlastní brandy
            "is_active":         True,
        })

    bq_upsert(client, tbl("brands"), rows, key_col="brand_id")
    return [b["id"] for b in brands]


def step_search_terms(client: bigquery.Client, brand_ids: list[str]) -> list[dict]:
    """
    GET /v1/metrics/search-terms → dim_search_terms
    Projde všechny brandy, vrátí sloučený seznam termů pro freshness check.
    Pozor: reálné klíče jsou "id" (ne searchTermId) a "term" (ne query).
    """
    log.info("━━ KROK 2: search_terms")
    all_rows  = []
    all_terms = []

    for brand_id in brand_ids:
        try:
            page_size = 5000
            data  = api_get("/v1/metrics/search-terms", {"brandId": brand_id, "limit": page_size})
            terms = data["data"]["searchTerms"]
            if len(terms) >= page_size:
                log.warning(f"    brand {brand_id}: vráceno přesně {page_size} termů — API možná cap-uje výsledky, skutečný počet může být vyšší")
            log.info(f"    brand {brand_id}: {len(terms)} search termů")
        except Exception as e:
            log.warning(f"    brand {brand_id}: API selhalo ({e}), přeskakuji — stávající záznamy v BQ zůstanou beze změny")
            continue

        rows = []
        for t in terms:
            topic = t.get("searchTermTopicRef") or {}
            rows.append({
                "search_term_id": t["id"],
                "brand_id":       brand_id,
                "query":          t.get("term"),
                "topic_id":       topic.get("id"),
                "topic_name":     topic.get("name"),
                "engine":         (t.get("aiSearchEngines") or [""])[0],
                "region":         t.get("region"),
                "interval":       t.get("interval"),
                "tags":           t.get("tags", []),
                "is_active":      t.get("status") == "active",
            })
        all_rows.extend(rows)
        all_terms.extend(terms)

        # UPSERT per brand — NOT MATCHED BY SOURCE platí jen pro tento brand_id
        bq_upsert(client, tbl("search_terms"), rows, key_col="search_term_id",
                  source_filter=f"T.`brand_id` = '{brand_id}'")

    log.info(f"    celkem {len(all_rows)} search termů")
    return all_terms


def step_brand_snapshots(client: bigquery.Client, brand_id: str) -> None:
    """
    POST /v1/metrics/search-terms-report → fact_brand_snapshots

    Jeden řádek = brand × search term × týdenní snapshot.
    Vlastní brand (ownBrand) + každý detekovaný competitor.
    snapshot_date = DATE(lastSnapshotAt) → partition overwrite zachová historii.
    """
    log.info("━━ KROK 3: brand_snapshots")
    ensure_fact_table(
        client, tbl("brand_snapshots"),
        schema=FACT_BRAND_SNAPSHOTS_SCHEMA,
        partition_field="snapshot_date",
        cluster_fields=["is_own_brand", "engine"],
    )
    data  = api_post("/v1/metrics/search-terms-report", {
        "brandId":            brand_id,
        "timeFrame":          TIME_FRAME,
        "periodOffset":       0,
        "selectedTopic":      "all",
        "selectedTags":       "all",
        "selectedEngine":     "all",
        "selectedQuery":      "all",
        "includeAnswerTexts": False,
    })
    terms = data["data"].get("searchTerms", [])
    log.info(f"    {len(terms)} search termů v response")

    rows = []
    for t in terms:
        last_snap = t.get("lastSnapshotAt")
        snap_date = snapshot_date_from(last_snap)
        snap_week = iso_week(last_snap)
        engine    = (t.get("aiSearchEngines") or [""])[0]
        topic     = t.get("topic") or {}

        def make_row(brand_data: dict, is_own: bool) -> dict:
            return {
                "snapshot_date":   snap_date,
                "snapshot_week":   snap_week,
                "search_term_id":  t["searchTermId"],
                "brand_name":      brand_data.get("name") or "unknown",  # REQUIRED – nesmí být NULL
                "is_own_brand":    is_own,
                "brand_id":        brand_id if is_own else None,
                "visibility_score": brand_data.get("visibilityScore"),
                "avg_sentiment":    brand_data.get("avgSentiment"),
                "avg_rank":         brand_data.get("avgRank"),
                "latest_rank":      brand_data.get("latestRank"),
                "detection_rate":   brand_data.get("detectionRate"),
                "top3_rate":        brand_data.get("top3"),
                "citation_count":   brand_data.get("citationCount"),
                "appearances":      brand_data.get("appearances"),
                "engine":           engine,
                "topic_id":         topic.get("id"),
                "last_snapshot_at": last_snap,
            }

        if "ownBrand" in t:
            rows.append(make_row(t["ownBrand"], is_own=True))

        for comp in t.get("competitors", []):
            rows.append(make_row(comp, is_own=False))

    log.info(f"    {len(rows)} řádků celkem (vlastní brand + competitors)")
    bq_partition_overwrite(client, tbl("brand_snapshots"), rows, date_col="snapshot_date")


def step_answer_texts(client: bigquery.Client, brand_id: str) -> None:
    """
    POST /v1/metrics/search-terms-report (includeAnswerTexts: true) → fact_answer_texts
    Append + dedup podle execution_id (exekuce jsou unikátní navždy).
    """
    log.info("━━ KROK 4: answer_texts")
    ensure_fact_table(
        client, tbl("answer_texts"),
        schema=FACT_ANSWER_TEXTS_SCHEMA,
        partition_field="executed_at",
        cluster_fields=["engine"],
    )
    data  = api_post("/v1/metrics/search-terms-report", {
        "brandId":            brand_id,
        "timeFrame":          TIME_FRAME,
        "periodOffset":       0,
        "selectedTopic":      "all",
        "selectedTags":       "all",
        "selectedEngine":     "all",
        "selectedQuery":      "all",
        "includeAnswerTexts": True,
    })
    terms = data["data"].get("searchTerms", [])

    rows = []
    for t in terms:
        for at in t.get("answerTexts") or []:
            rows.append({
                "execution_id":   at["executionId"],
                "search_term_id": t["searchTermId"],
                "executed_at":    at.get("executedAt"),
                "engine":         at.get("engine"),
                "answer_text":    at.get("answerText"),
            })

    log.info(f"    {len(rows)} answer textů k zpracování")
    bq_append_dedup(client, tbl("answer_texts"), rows, dedup_col="execution_id")


def step_citations(client: bigquery.Client, brand_id: str) -> None:
    """
    POST /v1/metrics/citations → citations

    Zdroj: domainSummary.topDomainsByQuery — nejgranularnější data (per query × engine × domain × url).
    Jeden řádek = url × engine × search term × snapshot.
    """
    log.info("━━ KROK 5: citations")
    ensure_fact_table(
        client, tbl("citations"),
        schema=FACT_CITATIONS_SCHEMA,
        partition_field="snapshot_date",
        cluster_fields=["brand_id", "engine", "domain"],
    )
    data = api_post("/v1/metrics/citations", {
        "brandId":        brand_id,
        "timeFrame":      TIME_FRAME,
        "periodOffset":   0,
        "selectedTopic":  "all",
        "selectedEngine": "all",
        "selectedQuery":  "all",
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
                            "snapshot_date":  TODAY,
                            "snapshot_week":  iso_week(NOW),
                            "brand_id":       brand_id,
                            "search_term_id": search_term_id,
                            "engine":         engine,
                            "domain":         domain,
                            "url":            url_entry.get("url"),
                            "occurrences":    url_entry.get("occurrences", 0),
                        })
                else:
                    rows.append({
                        "snapshot_date":  TODAY,
                        "snapshot_week":  iso_week(NOW),
                        "brand_id":       brand_id,
                        "search_term_id": search_term_id,
                        "engine":         engine,
                        "domain":         domain,
                        "url":            None,
                        "occurrences":    occurrences,
                    })

    log.info(f"    {len(rows)} citačních záznamů")
    bq_partition_overwrite(client, tbl("citations"), rows, date_col="snapshot_date")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    log.info("╔══════════════════════════════════════════════╗")
    log.info(f"║  Rankscale ETL  –  {TODAY}  TIME_FRAME={TIME_FRAME}  ║")
    log.info("╚══════════════════════════════════════════════╝")

    client = get_bq_client()

    brand_ids = step_brands(client)
    log.info(f"    brand_ids = {brand_ids}")

    terms = step_search_terms(client, brand_ids)

    if has_new_snapshots(client, terms):
        for brand_id in brand_ids:
            log.info(f"━━ Zpracovávám brand {brand_id}")
            step_brand_snapshots(client, brand_id)
            step_answer_texts(client, brand_id)
            step_citations(client, brand_id)
    else:
        log.info("    Žádná nová data – kroky 3, 4 a 5 přeskočeny")

    log.info("╔══════════════════════════════════════════════╗")
    log.info("║  ETL dokončen  ✓                             ║")
    log.info("╚══════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
