# Rankscale Metrics API — Dokumentace

**Base URL:** `https://rankscale.ai`  
**Verze:** v1  
**Plán:** Agency Growth nebo Enterprise

---

## Autentizace

Každý request vyžaduje API klíč v hlavičce:

```http
Authorization: Bearer rk_tvuj_api_klic
```

API klíč najdeš v Rankscale: **Settings → API Access**

> Metrics API klíč je **oddělený** od Share Links API klíče.

---

## Společné parametry — časové okno

Většina POST endpointů přijímá časové parametry. Použij **buď** `timeFrame`, **nebo** `isoStartDate` + `isoEndDate` — nikdy obojí najednou.

### timeFrame

| Hodnota | Popis |
|---|---|
| `24h` | Posledních 24 hodin |
| `7d` | Posledních 7 dní |
| `30d` | Posledních 30 dní |
| `3m` | Poslední 3 měsíce |
| `1y` | Poslední rok |

### Vlastní datum range

```json
{
  "isoStartDate": "2026-01-01",
  "isoEndDate":   "2026-03-31"
}
```

### periodOffset

Posun o N period zpět. Např. `timeFrame: "7d"` + `periodOffset: 1` = předminulý týden.

---

## Přehled endpointů

| Endpoint | Metoda | Byznys účel |
|---|---|---|
| `/v1/metrics/brands` | GET | Zjisti, které brandy sleduješ |
| `/v1/metrics/search-terms` | GET | Seznam všech promptů per brand |
| `/v1/metrics/search-terms-report` | POST | Metriky brandů per prompt (hlavní endpoint) |
| `/v1/metrics/citations` | POST | Které weby AI citoval v odpovědích |
| `/v1/metrics/report` | POST | Souhrnné metriky celého brandu |
| `/v1/metrics/sentiment` | POST | Klíčová slova sentimentu v AI odpovědích |
| `/v1/metrics/topics` | GET | Seznam produktových vertikál |
| `/v1/metrics/credits` | GET | Stav kreditů workspace |

---

## GET /v1/metrics/brands

### Byznys účel

Vrátí seznam všech brandů, které monitoruješ v Rankscale workspace. **Volej jako první** — potřebuješ `brand_id` pro všechny ostatní endpointy.

Vrátí pouze **vlastní brandy** (ne competitors). Competitors se objevují jako detekovaná konkurence v odpovědích `/search-terms-report`.

### Request

```http
GET /v1/metrics/brands?limit=1000
Authorization: Bearer rk_...
```

### Parametry

| Parametr | Typ | Popis |
|---|---|---|
| `limit` | integer | Max počet vrácených brandů |

### Klíčová pole response

| Pole | Typ | Popis |
|---|---|---|
| `brands[].id` | string | **Brand ID** — použij jako `brandId` v ostatních endpointech |
| `brands[].name` | string | Název brandu |
| `brands[].url` | string | Hlavní URL brandu |
| `brands[].operationalTopics[]` | array | Přiřazené produktové vertikály |
| `brands[].syncSchedules` | object | Plán spouštění snapshotů (`weekly.weekday`, `daily.hour`) |

### Využití v pipeline

Krok 1 v `rankscale_extract.py` — stáhne brand_id a použije je ve všech dalších krocích.

---

## GET /v1/metrics/search-terms

### Byznys účel

Vrátí seznam všech sledovaných promptů pro daný brand. Každý záznam reprezentuje **1 prompt × 1 AI engine** — stejný text promptu se opakuje tolikrát, na kolika enginech běží.

Tento endpoint nevrací metriky — jen seznam promptů s jejich konfigurací (topic, tagy, frekvence).

### Request

```http
GET /v1/metrics/search-terms?brandId=E5GAVmqco65u7Smx3hso&limit=5000
Authorization: Bearer rk_...
```

### Parametry

| Parametr | Typ | Povinný | Popis |
|---|---|---|---|
| `brandId` | string | ✅ | ID brandu z `/brands` |
| `limit` | integer | | Max počet záznamů — nastav na `5000` aby ses vyhnul stránkování |

### Klíčová pole response

| Pole | Typ | Popis |
|---|---|---|
| `searchTerms[].id` | string | **Search term ID** — unikátní per prompt × engine |
| `searchTerms[].term` | string | Text promptu (pozor: pole se jmenuje `term`, ne `query`) |
| `searchTerms[].aiSearchEngines[0]` | string | Engine — vždy jen jeden (`chatgpt_gui`, `google_ai_mode_gui`...) |
| `searchTerms[].status` | string | `"active"` nebo `"inactive"` |
| `searchTerms[].interval` | string | Frekvence: `"weekly"` nebo `"daily"` |
| `searchTerms[].region` | string | Region: `"cz"`, `"sk"`... |
| `searchTerms[].searchTermTopicRef.id` | string | ID produktové vertikály |
| `searchTerms[].searchTermTopicRef.name` | string | Název vertikály |
| `searchTerms[].tags` | array | Pole štítků, např. `["product-brand", "top-funnel"]` |
| `searchTerms[].lastExecutionTime` | timestamp | Kdy byl prompt naposledy spuštěn |
| `searchTerms[].nextScheduledExecutionTime` | timestamp | Kdy bude spuštěn příště |
| `searchTerms[].executionsAmount` | integer | Celkový počet spuštění |

### Hodnoty engine

| Hodnota | AI engine |
|---|---|
| `chatgpt_gui` | ChatGPT |
| `perplexity_gui` | Perplexity |
| `google_gemini_gui` | Google Gemini |
| `google_ai_overview` | Google AI Overview |
| `google_ai_mode_gui` | Google AI Mode |
| `bing_copilot_gui` | Bing Copilot |
| `xai_grok_gui` | Grok (xAI) |

### Využití v pipeline

Krok 2 v `rankscale_extract.py` — naplňuje `raw_search_terms`. Slouží jako číselník promptů pro L1_dim_search_terms.

---

## POST /v1/metrics/search-terms-report

### Byznys účel

**Hlavní endpoint pro metriky.** Vrátí výkonnostní metriky pro každý prompt — jak pro vlastní brand, tak pro všechny competitors detekované v AI odpovědích.

Odpovídá na otázky:
- Jak se zobrazuje náš brand v AI odpovědích na jednotlivé prompty?
- Kdo jsou naši competitors v daných tématech?
- Jaká je naše pozice, visibility a sentiment?

Volitelně vrátí i plné texty AI odpovědí (`includeAnswerTexts: true`).

### Request

```http
POST /v1/metrics/search-terms-report
Authorization: Bearer rk_...
Content-Type: application/json
```

```json
{
  "brandId":            "E5GAVmqco65u7Smx3hso",
  "timeFrame":          "7d",
  "selectedTopic":      "all",
  "selectedTags":       "all",
  "selectedEngine":     "all",
  "selectedQuery":      "all",
  "includeAnswerTexts": false
}
```

### Parametry

| Parametr | Typ | Povinný | Popis |
|---|---|---|---|
| `brandId` | string | ✅ | ID brandu |
| `timeFrame` | string | | Časové okno (`7d`, `30d`, `1y`...) |
| `periodOffset` | integer | | Posun o N period zpět |
| `selectedTopic` | string | | ID topicu nebo `"all"` |
| `selectedTags` | string\|array | | Tagy nebo `"all"` |
| `selectedEngine` | string\|array | | Engine nebo `"all"` |
| `selectedQuery` | string | | ID konkrétního search termu nebo `"all"` |
| `isoStartDate` | string | | Vlastní začátek (přepíše `timeFrame`) |
| `isoEndDate` | string | | Vlastní konec (přepíše `timeFrame`) |
| `includeAnswerTexts` | boolean | | Pokud `true`, vrátí plné texty AI odpovědí |

### Klíčová pole response — search term

| Pole | Typ | Popis |
|---|---|---|
| `searchTerms[].searchTermId` | string | ID search termu |
| `searchTerms[].query` | string | Text promptu |
| `searchTerms[].lastSnapshotAt` | timestamp | Kdy byl naposledy spuštěn snapshot → `snapshot_date` v BQ |
| `searchTerms[].topic.id` | string | ID topicu (objekt, ne string!) |
| `searchTerms[].topic.name` | string | Název topicu |
| `searchTerms[].ownBrand` | object\|undefined | Metriky vlastního brandu — **chybí** pokud nebyl detekován |
| `searchTerms[].competitors[]` | array | Metriky competitors detekovaných v AI |
| `searchTerms[].answerTexts[]` | array | Texty odpovědí (jen pokud `includeAnswerTexts: true`) |

### Klíčová pole response — metriky brandu (ownBrand / competitors)

| Pole | Typ | Popis |
|---|---|---|
| `name` | string | Název brandu / competitors |
| `isOwnBrand` | boolean | TRUE = vlastní brand |
| `visibilityScore` | float | **0–100** — jak prominentně AI brand zmiňuje |
| `avgSentiment` | float | **0–100** — 50 = neutrální, >50 = pozitivní |
| `avgRank` | float | Průměrná pozice v AI odpovědi (1 = nejlepší) |
| `latestRank` | integer\|null | Pozice v posledním snapshotu (`null` = nenalezen) |
| `detectionRate` | float | % snapshotů kde byl brand detekován (0–100) |
| `top3` | float | % výskytů na pozici 1–3 (0–100) |
| `citationCount` | integer | Počet citovaných URL |
| `appearances` | integer | Počet snapshotů kde se brand objevil |
| `firstSeen` | timestamp | První detekce v daném období |
| `lastSeen` | timestamp | Poslední detekce v daném období |

### Klíčová pole response — answerTexts (pokud includeAnswerTexts: true)

| Pole | Typ | Popis |
|---|---|---|
| `executionId` | string | Unikátní ID konkrétní exekuce |
| `executedAt` | timestamp | Kdy AI engine odpověděl |
| `engine` | string | Který engine odpovídal |
| `answerText` | string | Plný text AI odpovědi (markdown) |

### Využití v pipeline

Krok 3 a 4 v `rankscale_extract.py`:
- Krok 3: `includeAnswerTexts: false` → naplňuje `raw_brand_snapshots`
- Krok 4: `includeAnswerTexts: true` → naplňuje `raw_answer_texts`

---

## POST /v1/metrics/citations

### Byznys účel

Vrátí přehled webů (domén a URL), které AI enginy citovaly jako zdroje v odpovědích na naše prompty. Odpovídá na otázky:

- Které weby AI zmiňuje jako zdroje v kontextu našich témat?
- Jaké URL z naší domény AI cituje?
- Které konkurenční weby se citují víc než my?

### Request

```http
POST /v1/metrics/citations
Authorization: Bearer rk_...
Content-Type: application/json
```

```json
{
  "brandId":   "E5GAVmqco65u7Smx3hso",
  "timeFrame": "7d"
}
```

### Parametry

| Parametr | Typ | Povinný | Popis |
|---|---|---|---|
| `brandId` | string | ✅ | ID brandu |
| `timeFrame` | string | | Časové okno |
| `periodOffset` | integer | | Posun o N period |
| `selectedTopic` | string | | Filtr topicu nebo `"all"` |
| `selectedEngine` | string\|array | | Filtr enginu nebo `"all"` |
| `selectedQuery` | string | | Filtr search termu nebo `"all"` |
| `isoStartDate` | string | | Vlastní začátek |
| `isoEndDate` | string | | Vlastní konec |

### Klíčová pole response

| Pole | Typ | Popis |
|---|---|---|
| `totalCitations` | integer | Celkový počet citací |
| `uniqueDomains` | integer | Počet unikátních citovaných domén |
| `domainSummary.topDomainsOverall[]` | array | Top domény celkově |
| `domainSummary.topDomainsByEngine[]` | array | Top domény per AI engine |
| `domainSummary.topDomainsByQuery[]` | array | Top domény per prompt — **toto používáme v pipeline** |
| `domainSummary.topDomainsByOwnBrandCitations[]` | array | Top domény citující náš vlastní brand |
| `domainSummary.topDomainsByCompetitor[]` | array | Top domény per competitor |

Každá doména má:

| Pole | Typ | Popis |
|---|---|---|
| `domain` | string | Název domény, např. `banky.cz` |
| `occurrences` | integer | Počet výskytů |
| `urls[]` | array | Nejcitovanější URL z této domény |
| `urls[].url` | string | Konkrétní URL |
| `urls[].occurrences` | integer | Počet výskytů URL |

### Využití v pipeline

Krok 5 v `rankscale_extract.py` — naplňuje `raw_citations`. Používá `topDomainsByQuery` pro mapování citací na konkrétní prompty.

---

## POST /v1/metrics/report

### Byznys účel

Souhrnné metriky pro celý brand — na rozdíl od `/search-terms-report` nerozpadá data per prompt, ale agreguje vše dohromady. Vrátí timeline vlastního brandu, breakdown per topic a engine, a snapshot konkurence.

Vhodný pro **celkový přehled výkonnosti brandu** bez detailu na úrovni promptů.

### Request

```http
POST /v1/metrics/report
Authorization: Bearer rk_...
Content-Type: application/json
```

```json
{
  "brandId":        "E5GAVmqco65u7Smx3hso",
  "timeFrame":      "30d",
  "aggregation":    "weekly",
  "selectedTopic":  "all",
  "selectedEngine": "all"
}
```

### Parametry

| Parametr | Typ | Povinný | Popis |
|---|---|---|---|
| `brandId` | string | ✅ | ID brandu |
| `timeFrame` | string | | Časové okno |
| `aggregation` | string | | Granularita výsledků: `hourly`, `daily`, `weekly`, `monthly` |
| `periodOffset` | integer | | Posun o N period |
| `selectedTopic` | string | | Filtr topicu nebo `"all"` |
| `selectedTags` | string\|array | | Filtr tagů nebo `"all"` |
| `selectedEngine` | string\|array | | Filtr enginu nebo `"all"` |
| `selectedQuery` | string | | Filtr promptu nebo `"all"` |
| `isoStartDate` | string | | Vlastní začátek |
| `isoEndDate` | string | | Vlastní konec |

### Klíčová pole response

| Část response | Co obsahuje |
|---|---|
| `ownBrandMetrics` | Souhrnné metriky vlastního brandu (visibility, sentiment, rank...) |
| `ownBrandMetrics.trends` | Změna metrik oproti předchozímu období |
| `ownBrandMetrics.historicalData.weekly[]` | Timeline metrik po týdnech (paralelní pole hodnot + timestamps) |
| `ownBrandMetrics.topicMetricsData.weekly[]` | Timeline per produktová vertikála |
| `ownBrandMetrics.engineMetricsData.weekly[]` | Timeline per AI engine |
| `competitorMetrics[]` | Aktuální snapshot všech competitors (+ vlastní brand jako první prvek) |
| `competitorTimeSeriesData.weekly[]` | Timeline metrik competitors |

### Využití v pipeline

**Nepoužíváme v extraktu** — pro naše účely je `/search-terms-report` detailnější. `/report` by se hodil pokud bys chtěl rychlý celkový přehled bez rozkładu per prompt.

---

## POST /v1/metrics/sentiment

### Byznys účel

Vrátí klíčová slova sentimentu — konkrétní výrazy a fráze, které AI enginy používají při zmínkách o brandech. Rozlišuje pozitivní, neutrální a negativní klíčová slova a umí je rozdělit dle zdroje (webové vyhledávání vs. trénovací data).

Odpovídá na otázky:
- Proč je sentiment našeho brandu pozitivní / negativní?
- Jaká konkrétní slova AI spojuje s naším brandem?
- Jak se liší sentiment per AI engine?

### Request

```http
POST /v1/metrics/sentiment
Authorization: Bearer rk_...
Content-Type: application/json
```

```json
{
  "brandId":   "E5GAVmqco65u7Smx3hso",
  "timeFrame": "30d"
}
```

### Parametry

| Parametr | Typ | Povinný | Popis |
|---|---|---|---|
| `brandId` | string | ✅ | ID brandu |
| `timeFrame` | string | | Časové okno |
| `periodOffset` | integer | | Posun o N period |
| `selectedTopic` | string | | Filtr topicu nebo `"all"` |
| `selectedEngine` | string\|array | | Filtr enginu nebo `"all"` |
| `selectedQuery` | string | | Filtr promptu nebo `"all"` |

### Klíčová pole response

| Pole | Typ | Popis |
|---|---|---|
| `brandSentiments[].name` | string | Název brandu |
| `brandSentiments[].isOwnBrand` | boolean | TRUE = vlastní brand |
| `brandSentiments[].avgSentiment` | float | Průměrný sentiment **0–100** |
| `brandSentiments[].positiveKeywords` | object | Klíč = slovo, hodnota = `{count, executionIds[], timestamps[]}` |
| `brandSentiments[].neutralKeywords` | object | Stejná struktura |
| `brandSentiments[].negativeKeywords` | object | Stejná struktura |
| `brandSentiments[].webGroundingKeywords` | object | Klíčová slova z webového vyhledávání (positive/neutral/negative/byEngine) |
| `brandSentiments[].webGroundingSentimentByEngine` | object | Sentiment per engine z webových zdrojů (`sum`, `count`, `avg`) |

### Využití v pipeline

**Nepoužíváme v extraktu** — data ze sentiment endpointu nejsou v raw_ tabulkách. Pokud by bylo potřeba, lze přidat jako další krok extrakce.

---

## GET /v1/metrics/topics

### Byznys účel

Vrátí seznam všech produktových vertikál (topiců) pro daný brand. Každý topic obsahuje seznam přiřazených search term IDs. Slouží jako číselník pro filtrování v reporting endpointech.

### Request

```http
GET /v1/metrics/topics?brandRef=E5GAVmqco65u7Smx3hso
Authorization: Bearer rk_...
```

### Parametry

| Parametr | Typ | Povinný | Popis |
|---|---|---|---|
| `brandRef` | string | ✅ | ID brandu (pozor: parametr se jmenuje `brandRef`, ne `brandId`) |

### Klíčová pole response

| Pole | Typ | Popis |
|---|---|---|
| `topics[].id` | string | **Topic ID** — použij jako `selectedTopic` v reporting endpointech |
| `topics[].name` | string | Název topicu, např. `"Hypotéky"`, `"Půjčky"` |
| `topics[].searchTermIds[]` | array | ID search termů přiřazených k tomuto topicu |

### Využití v pipeline

**Nepoužíváme v extraktu** — topic informace jsou součástí `/search-terms` response (`searchTermTopicRef`). Endpoint by byl užitečný pokud bys chtěl stahovat data per topic.

---

## GET /v1/metrics/credits

### Byznys účel

Zjisti aktuální stav kreditů workspace a odhad jak dlouho kredity vydrží při aktuální spotřebě. Užitečné pro monitoring a alerting.

### Request

```http
GET /v1/metrics/credits
Authorization: Bearer rk_...
```

### Klíčová pole response

| Pole | Typ | Popis |
|---|---|---|
| `rankCredits` | integer | Aktuální počet kreditů |
| `runway.estimatedRunwayHours` | float | Odhad hodin než dojdou kredity |
| `runway.breakdown.weekly` | integer | Počet weekly exekucí per periodu |
| `dashboardRunway.isRunwayWarning` | boolean | TRUE = kredity se blíží konci |
| `dashboardRunway.metrics.creditsPerDay` | float | Průměrná denní spotřeba |

---

## Chybové kódy

| HTTP status | Popis |
|---|---|
| `200` | Úspěch |
| `400` | Chybějící nebo neplatné parametry |
| `401` | Neplatný API klíč |
| `403` | Přístup není povolen pro váš plán |
| `429` | Rate limit překročen (max 200 req/min) — implementuj retry s backoffem |
| `500` | Chyba na serveru Rankscale |

---

## Rate limiting

**200 requestů / minuta / API klíč.** Při překročení dostaneš `429 Too Many Requests`.

V pipeline čekáme `0.5s` mezi voláními (`RATE_SLEEP = 0.5`).

---

## Co v pipeline používáme a co ne

| Endpoint | Používáme | Proč |
|---|---|---|
| `GET /brands` | ✅ Krok 1 | Zjistíme brand_id |
| `GET /search-terms` | ✅ Krok 2 | Číselník promptů |
| `POST /search-terms-report` | ✅ Kroky 3+4 | Metriky + texty odpovědí |
| `POST /citations` | ✅ Krok 5 | Citované weby |
| `POST /report` | ❌ | Agregát bez detailu per prompt — nepotřebujeme |
| `POST /sentiment` | ❌ | Keyword detail — prozatím nepotřebujeme |
| `GET /topics` | ❌ | Topic info je v `/search-terms` response |
| `GET /credits` | ❌ | Lze přidat pro monitoring kreditů |
