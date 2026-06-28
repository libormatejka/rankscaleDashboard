# ETL – Strategie načítání dat do BigQuery

## Přehled

Každá tabulka má jinou strategii zápisu podle toho, jaká data obsahuje a jak se mění.

| Tabulka | Strategie | Funkce v kódu |
|---|---|---|
| `brands` | UPSERT | `bq_upsert()` |
| `search_terms` | UPSERT | `bq_upsert()` |
| `brand_snapshots` | PARTITION OVERWRITE | `bq_partition_overwrite()` |
| `answer_texts` | APPEND + dedup | `bq_append_dedup()` |
| `citations` | PARTITION OVERWRITE | `bq_partition_overwrite()` |

---

## UPSERT — `brands`, `search_terms`

**Co dělá:** Přes staging tabulku + MERGE DML:
- Existující záznamy → UPDATE (aktualizují se hodnoty)
- Nové záznamy → INSERT
- Záznamy chybějící v API (smazané v Rankscale) → `is_active = FALSE` (řádek zůstane v tabulce)

**Proč:** Při TRUNCATE by smazání brandu nebo promptu v Rankscale způsobilo ztrátu řádku v dimenzi. Historická data ve fact tabulkách by pak nešla joinovat na dimenzi. UPSERT zachová smazané záznamy s příznakem `is_active = FALSE`.

**Jak filtrovat aktivní záznamy v reportech:**
```sql
WHERE is_active = TRUE
```

**Staging tabulky:** BigQuery MERGE vyžaduje jako zdroj tabulku — nelze mergovat přímo Python list. ETL proto před každým MERGE vytvoří pomocné tabulky `brands_staging` a `search_terms_staging` (WRITE_TRUNCATE). Po MERGE zůstanou v datasetu, ale při příštím runu se přepíšou. Jejich obsah je vždy identický s tím, co se právě nahrávalo — lze je ignorovat.

---

## PARTITION OVERWRITE — `brand_snapshots`, `citations`

**Co dělá:** Data se rozdělí podle datumu (`snapshot_date`). Každý unikátní datum = jedna partition. ETL přepíše jen partitions které jsou v aktuálním stažení — starší historická data zůstanou nedotčena.

**Příklad:** ETL stahuje `TIME_FRAME = 7d`. Pokud jsou v datech dates `2026-06-12` až `2026-06-18`, přepíše se pouze těchto 7 partitions. Data z `2026-06-01` zůstanou.

**Proč:** Rankscale může zpětně upravit hodnoty v posledních dnech (přepočet metrik). Překryv 7 dní zajistí že vždy máme aktuální čísla, ale nemusíme přepisovat celou tabulku.

**Proč ne TRUNCATE:** Tabulky rostou — `brand_snapshots` přibírá ~2 300 řádků týdně per brand. Po roce by TRUNCATE a znovunaplnění bylo zbytečně drahé.

**Proč ne APPEND:** Bez přepisu partition by se při opakovaném runu duplikovaly řádky pro stejný datum.

---

## APPEND + dedup — `answer_texts`

**Co dělá:** Před zápisem se z BQ načtou všechna existující `execution_id`. Z nových dat se odfiltrují ty, které už v BQ jsou. Zapíší se jen skutečně nové záznamy.

**Proč:** Každá AI odpověď má unikátní `execution_id` přidělené Rankscalem — jednou vygenerovaná odpověď se nikdy nemění ani neobjevuje znovu. Stačí tedy zkontrolovat jestli ID už existuje, a pokud ano, přeskočit ho.

**Proč ne PARTITION OVERWRITE:** Answer texts se nesmažou ani nepřepisují — jsou to historické záznamy. Kdybychom přepsali partition, ztratili bychom texty odpovědí ze starších exekucí které aktuální `TIME_FRAME` nezahrnuje.

**Nevýhoda:** Při velkém množství dat je SELECT všech `execution_id` pomalý. Pokud tabulka naroste na miliony řádků, bude potřeba optimalizovat (např. SELECT jen za posledních 30 dní).

---

## Freshness check — proč se kroky 3–5 někdy přeskočí

Před spuštěním kroků 3–5 skript porovná:
- `MAX(last_snapshot_at)` z BQ tabulky `brand_snapshots`
- `MAX(lastExecutionTime)` z právě stažených search termů (krok 2, bez extra API callu)

Pokud jsou data v BQ stejně stará nebo novější než co Rankscale nabízí → kroky 3, 4 a 5 se přeskočí.

**Proč:** Rankscale spouští snapshoty týdně. ETL běží denně. 6 ze 7 dní tedy není co nového stahovat — freshness check ušetří 3 zbytečné API cally.

---

## Proč load jobs místo streaming insertů

BigQuery má dva způsoby zápisu:
- **Streaming insert** (`insert_rows_json`) — data jdou do dočasného bufferu, který se vyprázdní za hodiny
- **Load job** (používáme) — data jdou přímo do table storage

Dokud je streaming buffer neprázdný, nelze na daných řádcích dělat DELETE ani partition overwrite. Proto používáme load jobs — žádný buffer, žádné omezení.
