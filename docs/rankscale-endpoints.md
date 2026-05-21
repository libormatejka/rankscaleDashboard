# Rankscale Metrics API – Dokumentace endpointů

**Base URL:** `https://rankscale.ai`
**Verze:** v1
**Dostupnost:** Agency Growth a Enterprise plány

### Stav ověření endpointů

| Endpoint | Stav | Poznámka |
|---|---|---|
| `GET /v1/metrics/brands` | ✅ Ověřeno | Reálný response k dispozici |
| `GET /v1/metrics/search-terms` | ✅ Ověřeno | Reálný response k dispozici |
| `POST /v1/metrics/report` | ✅ Ověřeno | Reálný response k dispozici |
| `POST /v1/metrics/search-terms-report` | ✅ Ověřeno | Reálný response k dispozici |
| `POST /v1/metrics/sentiment` | ⏳ Čeká | Struktura z oficiální dokumentace |
| `POST /v1/metrics/citations` | ⏳ Čeká | Struktura z oficiální dokumentace |

---

## Obsah

- [Autentizace](#autentizace)
- [Konvence](#konvence)
- [Časová okna a agregace](#časová-okna-a-agregace)
- [Filtrování](#filtrování)
- [Rate limiting](#rate-limiting)
- [Endpointy](#endpointy)
  - [GET /v1/metrics/brands](#get-v1metricsbrands)
  - [GET /v1/metrics/search-terms](#get-v1metricssearch-terms)
  - [POST /v1/metrics/report](#post-v1metricsreport)
  - [POST /v1/metrics/search-terms-report](#post-v1metricssearch-terms-report)
  - [POST /v1/metrics/sentiment](#post-v1metricssentiment)
  - [POST /v1/metrics/citations](#post-v1metricscitations)
- [Chybové kódy](#chybové-kódy)

---

## Autentizace

Všechny requesty vyžadují API klíč scopovaný na workspace.

### Bearer header (doporučeno)
```http
Authorization: Bearer rk_your_api_key_here
```

### Query parametr (alternativa)
```
?api_key=rk_your_api_key_here
```

---

## Konvence

- Každý response obsahuje hlavičku **`X-Request-Id`** pro debugging
- Chybový response má vždy stejnou strukturu:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "brandId is required",
    "requestId": "req_abc123"
  }
}
```

---

## Časová okna a agregace

### Předdefinovaná časová okna (`timeFrame`)

| Hodnota | Popis |
|---|---|
| `24h` | Posledních 24 hodin |
| `7d` | Posledních 7 dní |
| `30d` | Posledních 30 dní |
| `3m` | Poslední 3 měsíce |
| `1y` | Poslední rok |

### Agregace (`aggregation`)

| Hodnota | Popis |
|---|---|
| `hourly` | Po hodinách |
| `daily` | Po dnech |
| `weekly` | Po týdnech |
| `monthly` | Po měsících |

### Vlastní datum range

Pokud zadáš **oboje** `isoStartDate` + `isoEndDate`, přepíší `timeFrame` a `periodOffset`.

```json
{
  "isoStartDate": "2026-03-01",
  "isoEndDate": "2026-03-31"
}
```

> ⚠️ Nikdy nekombinuj vlastní date range s `timeFrame` – použij jedno nebo druhé.

---

## Filtrování

### Podle tagů
```json
{
  "filters": {
    "tags": ["tag1", "tag2"]
  }
}
```
- Logika je **OR** – search term se zahrne pokud má **libovolný** z uvedených tagů
- Pro search terms **bez tagu** použij speciální hodnotu `__UNTAGGED__`

### Podle topicu
```json
{
  "filters": {
    "topicId": "nazev-topicu"
  }
}
```
- Lze filtrovat vždy jen jeden topic
- Pro search terms **bez topicu** použij speciální hodnotu `_orphaned`

### Kombinace
```json
{
  "filters": {
    "tags": ["__UNTAGGED__"],
    "topicId": "_orphaned"
  }
}
```

---

## Rate limiting

**Limit:** 200 requestů / minuta / API klíč

Každý response vrací hlavičky:
```
X-RateLimit-Limit: 200
X-RateLimit-Remaining: 195
X-RateLimit-Reset: 1706785200
```

Při překročení limitu dostaneš `429 Too Many Requests`. Implementuj exponential backoff.

> 💡 Doporučení: čekej minimálně **0.4 s** mezi voláními jako buffer.

---

## Endpointy

---

### GET /v1/metrics/brands

Vrátí seznam všech brandů v workspace včetně jejich topics, search terms a tagů. **Volej jako první** – potřebuješ `brand_id` pro ostatní endpointy.

> ✅ **Ověřeno reálným API response.**

#### Request

```http
GET /v1/metrics/brands?limit=1000
Authorization: Bearer rk_your_api_key_here
```

#### Query parametry

| Parametr | Typ | Výchozí | Popis |
|---|---|---|---|
| `limit` | integer | – | Max počet vrácených brandů |

#### Response

```json
{
  "success": true,
  "data": {
    "brands": [
      {
        "id": "E5GAVmqco65u7Smx3hso",
        "name": "Česká spořitelna",
        "brandInfo": {
          "names": ["Česká spořitelna", "Spořka"],
          "productNames": [],
          "description": ""
        },
        "url": "https://www.csas.cz",
        "createdAt": "2026-01-26T18:53:11.123Z",
        "operationalTopics": [
          {
            "topicId": "truYnsoK6ygBo1Ekgmez",
            "name": "Investice",
            "addedAt": "2026-01-26T19:03:45.175Z"
          },
          {
            "topicId": "ZFyMrgG0cuuEAvCdf1nr",
            "name": "Brand",
            "addedAt": "2026-01-27T06:49:05.182Z"
          }
        ],
        "operationalSearchTerms": [
          {
            "searchTermId": "xS7FDRiCviDIlTtUg80f",
            "query": "Jaká je nejlepší banka v ČR?",
            "addedAt": "2026-01-27T06:51:41.069Z"
          }
        ],
        "operationalTags": ["dip", "investice"],
        "defaultCountry": "cz",
        "defaultLanguage": "cs",
        "syncSchedules": {
          "monthly": null,
          "weekly": { "weekday": "tue" },
          "daily": { "hour": 6 }
        }
      }
    ]
  }
}
```

#### Pole response

**`data.brands[]`** – základní info

| Pole | Typ | Popis |
|---|---|---|
| `id` | string | **Unikátní ID brandy** – používej jako `brandId` v ostatních requestech |
| `name` | string | Zobrazovaný název brandy |
| `url` | string | Hlavní URL brandy (celá URL včetně `https://`) |
| `createdAt` | timestamp | Datum vytvoření brandy v Rankscale |

**`brandInfo{}`** – alternativní názvy

| Pole | Typ | Popis |
|---|---|---|
| `brandInfo.names[]` | array | Všechny sledované varianty názvu brandy v AI odpovědích |
| `brandInfo.productNames[]` | array | Sledované názvy produktů |
| `brandInfo.description` | string | Popis brandy |

**`operationalTopics[]`** – přiřazené topicy

| Pole | Typ | Popis |
|---|---|---|
| `topicId` | string | **Unikátní ID topicu** – existuje, viz níže |
| `name` | string | Název topicu, např. `"Investice"`, `"Hypotéky"` |
| `addedAt` | timestamp | Kdy byl topic přidán k brandě |

> ⚠️ **Oprava dokumentace:** Topic ID **existuje** (`topicId`). Původní dokumentace uváděla že topic je jen string bez ID – to bylo chybné.

**`operationalSearchTerms[]`** – přiřazené search terms

| Pole | Typ | Popis |
|---|---|---|
| `searchTermId` | string | Unikátní ID search termu |
| `query` | string | Znění promptu |
| `addedAt` | timestamp | Kdy byl search term přidán |

> ⚠️ **Duplicity:** Stejný `searchTermId` se v poli může opakovat vícekrát s různými `addedAt` timestampy. Při zpracování deduplikuj podle `searchTermId`.

**`operationalTags[]`** – tagy brandy

| Pole | Typ | Popis |
|---|---|---|
| `operationalTags` | array of strings | Tagy přiřazené brandě, např. `["dip", "investice"]` |

**`syncSchedules{}`** – plán spouštění

| Pole | Typ | Popis |
|---|---|---|
| `syncSchedules.daily.hour` | integer | Hodina denního spouštění (UTC) |
| `syncSchedules.weekly.weekday` | string | Den týdenního spouštění, např. `"tue"` |
| `syncSchedules.monthly` | null \| object | Plán měsíčního spouštění |

**`defaultCountry` / `defaultLanguage`**

| Pole | Typ | Popis |
|---|---|---|
| `defaultCountry` | string | ISO kód výchozí země, např. `"cz"` |
| `defaultLanguage` | string | ISO kód výchozího jazyka, např. `"cs"` |

#### Co se liší oproti oficiální dokumentaci

| Oficiální dokumentace | Realita |
|---|---|
| `domain` | `url` – celá URL včetně `https://` |
| `variants[]` | `brandInfo.names[]` – alternativní názvy |
| `searchTermCount` | **neexistuje** – počet search terms nelze přímo odečíst |
| topic je jen string bez ID | `operationalTopics[].topicId` – **topic ID existuje** |
| search terms jsou pouze v `/search-terms` endpointu | `operationalSearchTerms[]` jsou **embedované přímo v brands response** (s duplikáty!) |
| tagy jsou na search termu | `operationalTags[]` jsou také na **úrovni brandy** |

---

### GET /v1/metrics/search-terms

Vrátí seznam všech search terms pro danou brandy.

> ✅ **Ověřeno reálným API response.**

> ⚠️ **Klíčové zjištění:** Každý záznam reprezentuje **1 prompt × 1 engine**. Stejný text promptu se tedy v odpovědi opakuje tolikrát, na kolika enginech běží. Pro získání unikátních promptů je nutné deduplikovat podle `term`.

#### Request

```http
GET /v1/metrics/search-terms?brandId=E5GAVmqco65u7Smx3hso&limit=1000
Authorization: Bearer rk_your_api_key_here
```

#### Query parametry

| Parametr | Typ | Povinný | Popis |
|---|---|---|---|
| `brandId` | string | ✅ | ID brandy z `/v1/metrics/brands` |
| `limit` | integer | | Max počet vrácených záznamů |

#### Response

```json
{
  "success": true,
  "data": {
    "searchTerms": [
      {
        "id": "xS7FDRiCviDIlTtUg80f",
        "term": "Jaká je nejlepší banka v ČR?",
        "aiSearchEngines": ["chatgpt_gui"],
        "status": "active",
        "executionsAmount": 13,
        "interval": "weekly",
        "region": "cz",
        "websearch": true,
        "createdAt": "2026-01-27T06:51:17.070Z",
        "lastExecutionTime": "2026-04-21T06:07:06.494Z",
        "nextScheduledExecutionTime": "2026-04-28T06:00:00.000Z",
        "searchTermTopicRef": {
          "id": "ZFyMrgG0cuuEAvCdf1nr",
          "name": "Brand"
        },
        "tags": []
      },
      {
        "id": "a4pXbk0OMnHGvZrWlBUi",
        "term": "Jaká je nejlepší banka v ČR?",
        "aiSearchEngines": ["perplexity_gui"],
        "status": "active",
        "executionsAmount": 13,
        "interval": "weekly",
        "region": "cz",
        "websearch": true,
        "createdAt": "2026-01-27T06:51:17.072Z",
        "lastExecutionTime": "2026-04-21T06:06:14.929Z",
        "nextScheduledExecutionTime": "2026-04-28T06:00:00.000Z",
        "searchTermTopicRef": {
          "id": "ZFyMrgG0cuuEAvCdf1nr",
          "name": "Brand"
        },
        "tags": ["dip", "investice"]
      }
    ]
  }
}
```

#### Pole response

**`data.searchTerms[]`** – jeden záznam = 1 prompt × 1 engine

| Pole | Typ | Popis |
|---|---|---|
| `id` | string | **Unikátní ID tohoto záznamu** (prompt × engine kombinace) |
| `term` | string | **Znění promptu** (ne `query`!) |
| `aiSearchEngines` | array | Pole s **právě jedním** engine názvem, např. `["chatgpt_gui"]` |
| `status` | string | `"active"` nebo `"inactive"` (ne boolean!) |
| `executionsAmount` | integer | Celkový počet spuštění tohoto záznamu |
| `interval` | string | Frekvence: `"weekly"`, `"daily"` |
| `region` | string | Region: `"cz"`, `"us"` apod. |
| `websearch` | boolean | Zda engine používá webové vyhledávání |
| `createdAt` | timestamp | Datum vytvoření |
| `lastExecutionTime` | timestamp | Kdy byl naposledy spuštěn |
| `nextScheduledExecutionTime` | timestamp \| null | Kdy bude příště spuštěn (`null` u inactive) |
| `searchTermTopicRef.id` | string | **ID topicu** |
| `searchTermTopicRef.name` | string | Název topicu |
| `tags` | array | Pole tagů, může být prázdné `[]` |

#### Známé hodnoty `aiSearchEngines`

Z reálných dat (může být neúplné):

| Hodnota | Engine |
|---|---|
| `chatgpt_gui` | ChatGPT |
| `perplexity_gui` | Perplexity |
| `google_gemini_gui` | Google Gemini |
| `google_ai_overview` | Google AI Overview |
| `google_ai_mode_gui` | Google AI Mode |
| `bing_copilot_gui` | Bing Copilot |
| `xai_grok_gui` | Grok (xAI) |

#### Co se liší oproti oficiální dokumentaci

| Oficiální dokumentace | Realita |
|---|---|
| `query` | `term` |
| `engines[]` – pole více enginů na jeden záznam | `aiSearchEngines[]` – **vždy jen jeden engine** per záznam |
| `active: boolean` | `status: "active" \| "inactive"` |
| `topic: string` | `searchTermTopicRef: { id, name }` – **objekt s ID!** |
| Jeden záznam = jeden prompt | Jeden záznam = **1 prompt × 1 engine** |
| Pole `searchTermCount` na brandy | Chybí – počet zjistíš jen jako `length` tohoto pole |
| `nextScheduledExecutionTime` neexistuje | Existuje, `null` u inactive |
| `lastExecutionTime` neexistuje | Existuje |
| `executionsAmount` neexistuje | Existuje |
| `websearch` neexistuje | Existuje |

#### Request

```http
GET /v1/metrics/search-terms?brandId=brand_abc123&limit=1000
Authorization: Bearer rk_your_api_key_here
```

#### Query parametry

| Parametr | Typ | Povinný | Popis |
|---|---|---|---|
| `brandId` | string | ✅ | ID brandy z `/v1/metrics/brands` |
| `limit` | integer | | Max počet vrácených záznamů |

#### Response

```json
{
  "success": true,
  "data": {
    "searchTerms": [
      {
        "id": "st_abc123",
        "query": "kde koupit Hot Toys figury v ČR",
        "topic": "Hot Toys",
        "tags": ["funnel:top", "market:cz"],
        "engines": ["chatgpt", "gemini", "perplexity"],
        "interval": "daily",
        "region": "us",
        "active": true,
        "createdAt": "2024-07-01T08:00:00.000Z"
      }
    ],
    "pagination": {
      "total": 456,
      "limit": 1000,
      "offset": 0,
      "hasMore": false
    }
  }
}
```

#### Pole response

| Pole | Typ | Popis |
|---|---|---|
| `data.searchTerms[].id` | string | **Unikátní ID search termu** |
| `data.searchTerms[].query` | string | Přesné znění promptu zadávaného do AI |
| `data.searchTerms[].topic` | string | Název tematické skupiny (string, ne ID) |
| `data.searchTerms[].tags` | array | Štítky pro segmentaci |
| `data.searchTerms[].engines` | array | Enginy na kterých prompt běží |
| `data.searchTerms[].interval` | string | Frekvence spouštění: `"daily"`, `"hourly"` |
| `data.searchTerms[].region` | string | Geografický region |
| `data.searchTerms[].active` | boolean | Zda je search term aktivní |
| `data.searchTerms[].createdAt` | timestamp | Datum vytvoření |

> ⚠️ `brandId` se nevrací uvnitř každého záznamu – použij hodnotu z query parametru.

---

### POST /v1/metrics/report

Hlavní reporting endpoint. Vrací kompletní přehled metrik pro vlastní brand, historická data, breakdown per topic a engine, a metriky konkurence – vše v jednom volání.

> ✅ **Ověřeno reálným API response.**

> ⚠️ **Klíčová zjištění:**
> - Response je mnohem bohatší než dokumentace uvádí – obsahuje **vlastní brand, konkurenci i timeseries** najednou
> - Historická data jsou ve formátu **paralelních polí** (ne pole objektů)
> - `sentiment` je na škále **0–100**, ne 0–1
> - Endpoint vrací i **whitelist/blacklist** detekovaných konkurentů

#### Request

```http
POST /v1/metrics/report
Authorization: Bearer rk_your_api_key_here
Content-Type: application/json
```

```json
{
  "brandId": "E5GAVmqco65u7Smx3hso",
  "timeFrame": "30d",
  "aggregation": "daily",
  "periodOffset": 0,
  "selectedTopic": "all",
  "selectedTags": "all",
  "selectedEngine": "all",
  "selectedQuery": "all"
}
```

#### Tělo requestu

| Pole | Typ | Povinný | Popis |
|---|---|---|---|
| `brandId` | string | ✅ | ID brandy |
| `timeFrame` | string | | Časové okno: `24h`, `7d`, `30d`, `3m`, `1y` |
| `aggregation` | string | | Úroveň: `hourly`, `daily`, `weekly`, `monthly` |
| `periodOffset` | integer | | Posun o N period (0 = aktuální) |
| `selectedTopic` | string | | Topic ID nebo `"all"` |
| `selectedTags` | string\|array | | Tagy nebo `"all"` |
| `selectedEngine` | string\|array | | Engine nebo `"all"` |
| `selectedQuery` | string | | Search term ID nebo `"all"` |
| `isoStartDate` | string | | Vlastní začátek (přepíše `timeFrame`) |
| `isoEndDate` | string | | Vlastní konec (přepíše `timeFrame`) |

#### Response – přehled struktury

```json
{
  "success": true,
  "data": {
    "ownBrandMetrics": { ... },
    "competitorMetrics": [ ... ],
    "competitorTimeSeriesData": { ... }
  }
}
```

---

#### `data.ownBrandMetrics` – vlastní brand

**Souhrnné metriky** (aktuální snapshot)

```json
{
  "visibilityScore": 58,
  "sentiment": 61.5,
  "mentions": 717,
  "citations": 510,
  "avgPosition": 3.7,
  "detectionRate": 71.5,
  "top3": 39.2,
  "validMetricsCount": 4
}
```

| Pole | Typ | Popis |
|---|---|---|
| `visibilityScore` | float | Visibility skóre (0–100) |
| `sentiment` | float | Sentiment skóre (**0–100**, ne 0–1!) |
| `mentions` | integer | Celkový počet zmínek |
| `citations` | integer | Celkový počet citací |
| `avgPosition` | float | Průměrná pozice v AI odpovědích |
| `detectionRate` | float | % promptů kde se brand objevil (0–100) |
| `top3` | float | % výskytů v top 3 (0–100) |
| `validMetricsCount` | integer | Počet validních datových bodů |

**`trends{}`** – změna oproti předchozímu období (kladné = zlepšení)

```json
{
  "visibilityScore": 0.9,
  "sentiment": 0.2,
  "mentions": 6,
  "citations": -2,
  "avgPosition": -0.1,
  "detectionRate": 0.7,
  "top3": 1.4
}
```

**`historicalData{}`** – časová řada ve formátu paralelních polí

Response vždy obsahuje všechny čtyři klíče `hourly`, `daily`, `weekly`, `monthly`. Datová pole jsou vyplněna pouze pro úroveň odpovídající parametru `aggregation` v requestu – ostatní jsou prázdná pole `[]`.

```json
{
  "hourly":  { "visibilityScore": [], "sentiment": [], "mentions": [], "citations": [], "avgPosition": [], "detectionRate": [], "top3": [], "timestamps": [], "brandNotFound": [] },
  "daily": {
    "visibilityScore": [58.7, 57.2, 59.1],
    "sentiment":       [62.4, 62.4, 62.5],
    "mentions":        [180, 176, 182],
    "citations":       [124, 121, 119],
    "avgPosition":     [3.7, 3.7, 3.6],
    "detectionRate":   [72.1, 70.9, 72.4],
    "top3":            [39.2, 35.9, 39.1],
    "timestamps":      ["2026-04-07T00:00:00.000Z", "2026-04-14T00:00:00.000Z", "2026-04-21T00:00:00.000Z"],
    "brandNotFound":   [true, true, true]
  },
  "weekly":  { "visibilityScore": [], "sentiment": [], "mentions": [], "citations": [], "avgPosition": [], "detectionRate": [], "top3": [], "timestamps": [], "brandNotFound": [] },
  "monthly": { "visibilityScore": [], "sentiment": [], "mentions": [], "citations": [], "avgPosition": [], "detectionRate": [], "top3": [], "timestamps": [], "brandNotFound": [] }
}
```

> ⚠️ **`brandNotFound`** – `true` = v alespoň jednom snapshotu daného časového bucketu brand nebyl detekován (detection rate < 100%). `false` = brand byl nalezen ve **všech** snapshotech tohoto bucketu (detection rate = 100%). Hodnota `true` je tedy normální i u enginu s detection rate 70–90 %. Pouze engine s 100% detection rate má `false`.

**`topicMetricsData{}`** – breakdown per topic, stejný formát jako `historicalData`

Má stejné 4 klíče (`hourly`, `daily`, `weekly`, `monthly`). Neobsazené úrovně jsou prázdná pole `[]`. Aktivní úroveň je **pole objektů** (jeden per topic), každý se stejnou strukturou paralelních polí.

```json
{
  "hourly": [],
  "daily": [
    {
      "topicId": "ZFyMrgG0cuuEAvCdf1nr",
      "topicName": "Brand",
      "visibilityScore": [59.9, 58.4, 60.2],
      "sentiment":       [62.4, 62.4, 62.5],
      "avgPosition":     [3.7, 3.7, 3.6],
      "detectionRate":   [73.6, 72.4, 73.7],
      "top3":            [40, 36.6, 39.7],
      "mentions":        [180, 176, 181],
      "citations":       [124, 121, 118],
      "timestamps":      ["2026-04-07T00:00:00.000Z", "2026-04-14T00:00:00.000Z", "2026-04-21T00:00:00.000Z"],
      "brandNotFound":   [true, true, true]
    }
  ],
  "weekly": [],
  "monthly": []
}
```

**`engineMetricsData{}`** – breakdown per AI engine, stejný formát

Má stejné 4 klíče. Aktivní úroveň je **pole objektů** (jeden per engine). Obsahuje všechny enginy na kterých brand má aktivní search terms.

```json
{
  "hourly": [],
  "daily": [
    {
      "engineId": "chatgpt_gui",
      "engineName": "chatgpt_gui",
      "visibilityScore": [72.9, 73.9, 71.9],
      "sentiment":       [58.2, 59.6, 57.7],
      "avgPosition":     [3.2, 3.3, 3.3],
      "detectionRate":   [86.7, 88.9, 86.7],
      "top3":            [55.6, 48.9, 44.4],
      "mentions":        [38, 39, 38],
      "citations":       [19, 25, 24],
      "timestamps":      ["2026-04-07T00:00:00.000Z", "2026-04-14T00:00:00.000Z", "2026-04-21T00:00:00.000Z"],
      "brandNotFound":   [true, true, true]
    },
    {
      "engineId": "xai_grok_gui",
      "engineName": "xai_grok_gui",
      "visibilityScore": [80, 80, 66.7],
      "detectionRate":   [100, 100, 100],
      "brandNotFound":   [false, false, false]
    }
  ],
  "weekly": [],
  "monthly": []
}
```

**`preselectionWhitelist[]` / `preselectionBlacklist[]`** – entity detekované Rankscale

```json
{
  "preselectionWhitelist": ["Air Bank", "Raiffeisenbank", "CSOB", ...],
  "preselectionBlacklist": ["Home Credit", "Postovni sporitelna", ...],
  "manualWhitelist": [],
  "manualBlacklist": []
}
```

| Pole | Popis |
|---|---|
| `preselectionWhitelist` | Entity které Rankscale automaticky sleduje jako konkurenci |
| `preselectionBlacklist` | Entity vyloučené ze sledování |
| `manualWhitelist` / `manualBlacklist` | Ručně přidané výjimky |

---

#### `data.competitorMetrics[]` – snapshot konkurence

Jeden objekt per konkurent.

```json
{
  "name": "Air Bank",
  "isOwnBrand": false,
  "latestValue": 59.5,
  "trend": 0,
  "variations": ["Air Bank", "Air bank"],
  "visibilityScore": 59.5,
  "latestRank": 4.2,
  "avgRank": 3.4,
  "avgSentiment": 67.1,
  "appearances": 711,
  "citationCount": 515,
  "detectionRate": 70.8,
  "top3": 44,
  "validMetricsCount": 248
}
```

| Pole | Typ | Popis |
|---|---|---|
| `name` | string | Název konkurenta |
| `isOwnBrand` | boolean | `true` pro vlastní brand |
| `latestValue` | float | Aktuální visibility skóre |
| `trend` | float | Změna visibility oproti předchozímu období |
| `variations[]` | array | Všechny varianty názvu sledované v AI |
| `visibilityScore` | float | Visibility skóre (0–100) |
| `latestRank` | float | Aktuální průměrná pozice |
| `avgRank` | float | Průměrná pozice za celé období |
| `avgSentiment` | float | Průměrný sentiment (0–100) |
| `appearances` | integer | Celkový počet zmínek |
| `citationCount` | integer | Celkový počet citací |
| `detectionRate` | float | % promptů kde se brand objevil |
| `top3` | float | % výskytů v top 3 |
| `validMetricsCount` | integer | Počet validních datových bodů |

---

#### `data.competitorTimeSeriesData{}` – timeseries konkurence

Stejný formát paralelních polí, ale s `timestamps` na úrovni periody a `competitors[]` polem.

```json
{
  "daily": {
    "timestamps": ["2026-03-31T00:00:00.000Z", "2026-04-07T00:00:00.000Z", ...],
    "competitors": [
      {
        "name": "Air Bank",
        "isOwnBrand": false,
        "variations": ["Air Bank", "Air bank"],
        "metrics": {
          "visibilityScore": [59.2, 59.3, 59.5, 59.5],
          "sentiment":       [66.4, 66.6, 67.2, 67.1],
          "avgPosition":     [3.5, 3.4, 3.4, 3.4],
          "detectionRate":   [70.8, 70.6, 70.8, 70.8],
          "top3":            [42.9, 43.5, 44, 44],
          "mentions":        [179, 181, 176, 175],
          "citations":       [158, 152, 100, 105]
        }
      }
    ]
  }
}
```

#### Co se liší oproti oficiální dokumentaci

| Oficiální dokumentace | Realita |
|---|---|
| `data.summary{}` | Metriky přímo na `data.ownBrandMetrics{}` |
| `data.timeSeries[]` – pole objektů | `historicalData.daily{}` – paralelní pole hodnot |
| `data.byEngine{}` – klíče jako engine ID | `engineMetricsData.daily[]` – pole objektů |
| Endpoint vrací jen vlastní brand | Vrací **vlastní brand + konkurenci + timeseries** vše najednou |
| `sentiment` je 0–1 float | `sentiment` je **0–100** (např. `61.5`) |
| Bez `brandNotFound` | `brandNotFound[]` – paralelní boolean pole |
| Bez `topicMetricsData` | Topic breakdown je součástí response |
| Bez `competitorMetrics` | Konkurence je součástí response |
| Bez `preselectionWhitelist/Blacklist` | Whitelist/blacklist je součástí response |
| Bez `variations[]` | Každý brand má pole variant názvů |

#### Request

```http
POST /v1/metrics/report
Authorization: Bearer rk_your_api_key_here
Content-Type: application/json
```

```json
{
  "brandId": "brand_abc123",
  "timeFrame": "30d",
  "aggregation": "daily",
  "periodOffset": 0,
  "selectedTopic": "all",
  "selectedTags": "all",
  "selectedEngine": "all",
  "selectedQuery": "all"
}
```

#### Tělo requestu

| Pole | Typ | Povinný | Popis |
|---|---|---|---|
| `brandId` | string | ✅ | ID brandy |
| `timeFrame` | string | | Časové okno: `24h`, `7d`, `30d`, `3m`, `1y` |
| `aggregation` | string | | Úroveň agregace: `hourly`, `daily`, `weekly`, `monthly` |
| `periodOffset` | integer | | Posun o N period dozadu (0 = aktuální) |
| `selectedTopic` | string | | Filtr topicu nebo `"all"` |
| `selectedTags` | string\|array | | Filtr tagů nebo `"all"` |
| `selectedEngine` | string\|array | | Filtr enginů nebo `"all"` – např. `["chatgpt_gui", "perplexity_gui"]` |
| `selectedQuery` | string | | Filtr konkrétního search termu nebo `"all"` |
| `isoStartDate` | string | | Vlastní začátek: `"2026-03-01"` (přepíše `timeFrame`) |
| `isoEndDate` | string | | Vlastní konec: `"2026-03-31"` (přepíše `timeFrame`) |

#### Response

```json
{
  "success": true,
  "data": {
    "summary": {
      "avgVisibility": 42.5,
      "avgPosition": 3.2,
      "avgSentiment": 0.72,
      "totalMentions": 1284,
      "detectionRate": 68.3,
      "citationCount": 156,
      "top3Pct": 55.1
    },
    "timeSeries": [
      {
        "date": "2026-03-15T00:00:00.000Z",
        "visibility": 41.2,
        "position": 3.4,
        "sentiment": 0.71,
        "mentions": 89,
        "detectionRate": 67.0,
        "citations": 12,
        "top3Pct": 53.8
      }
    ],
    "byEngine": {
      "chatgpt": {
        "visibility": 45.0,
        "position": 2.8,
        "mentions": 320
      },
      "gemini": {
        "visibility": 38.5,
        "position": 3.6,
        "mentions": 280
      },
      "perplexity": {
        "visibility": 44.2,
        "position": 3.1,
        "mentions": 310
      }
    }
  },
  "meta": {
    "brandId": "brand_abc123",
    "timeFrame": "30d",
    "aggregation": "daily",
    "generatedAt": "2026-04-27T10:30:00.000Z"
  }
}
```

#### Pole response

**`data.summary`** – agregát za celé období

| Pole | Typ | Popis |
|---|---|---|
| `avgVisibility` | float | Průměrné visibility skóre (0–100) |
| `avgPosition` | float | Průměrná pozice v AI odpovědích |
| `avgSentiment` | float | Průměrný sentiment (**0–1**, ne procento) |
| `totalMentions` | integer | Celkový počet zmínek |
| `detectionRate` | float | % promptů kde se branda objevila |
| `citationCount` | integer | Počet citací |
| `top3Pct` | float | % výskytů v top 3 |

**`data.timeSeries[]`** – jeden záznam per agregační period

| Pole | Typ | Popis |
|---|---|---|
| `date` | timestamp | Datum periody |
| `visibility` | float | Visibility skóre (0–100) |
| `position` | float | Průměrná pozice |
| `sentiment` | float | Sentiment (**0–1**) |
| `mentions` | integer | Počet zmínek |
| `detectionRate` | float | Detection rate v % |
| `citations` | integer | Počet citací |
| `top3Pct` | float | % v top 3 |

**`data.byEngine{}`** – klíč je název enginu

| Pole | Typ | Popis |
|---|---|---|
| `[engine].visibility` | float | Visibility pro daný engine |
| `[engine].position` | float | Průměrná pozice |
| `[engine].mentions` | integer | Počet zmínek |

> ⚠️ `sentiment` je vždy **float 0–1** (např. `0.72`), nikoli procento. Pro zobrazení v % násob 100.

---

### POST /v1/metrics/search-terms-report

Metriky rozpadnuté na úroveň každého jednotlivého search termu. Pro každý search term vrací agregované metriky vlastního brandu (`ownBrand`) a seznam konkurentů (`competitors`) za zvolené časové období.

> ✅ **Ověřeno reálným API response.**

> ⚠️ **Klíčová zjištění:**
> - Struktura je **zásadně jiná** než dokumentace uváděla – žádný `latestRun`, `trend` ani `answerTexts`
> - Každý search term obsahuje `ownBrand{}` (volitelné – chybí pokud se brand neobjevil) a `competitors[]`
> - `topic` je **objekt** `{ id, name }`, ne string
> - Sentiment je na škále **0–100**, ne 0–1
> - `ownBrand` a každý competitor mají pole `variations[]` s variantami názvu (může být prázdné)

#### Request

```http
POST /v1/metrics/search-terms-report
Authorization: Bearer rk_your_api_key_here
Content-Type: application/json
```

```json
{
  "brandId": "E5GAVmqco65u7Smx3hso",
  "timeFrame": "7d"
}
```

#### Tělo requestu

| Pole | Typ | Povinný | Popis |
|---|---|---|---|
| `brandId` | string | ✅ | ID brandy |
| `timeFrame` | string | | Časové okno: `24h`, `7d`, `30d`, `3m`, `1y` |
| `periodOffset` | integer | | Posun o N period |
| `selectedTopic` | string | | Filtr topicu nebo `"all"` |
| `selectedTags` | string\|array | | Filtr tagů nebo `"all"` |
| `selectedEngine` | string\|array | | Filtr enginů nebo `"all"` |
| `selectedQuery` | string | | Filtr konkrétního search termu nebo `"all"` |
| `isoStartDate` | string | | Vlastní začátek (přepíše `timeFrame`) |
| `isoEndDate` | string | | Vlastní konec (přepíše `timeFrame`) |

#### Response

```json
{
  "success": true,
  "data": {
    "timeFrame": "7d",
    "requestedDateRange": {
      "source": "timeFrame",
      "startDate": "2026-04-20T18:12:39.670Z",
      "endDate": "2026-04-27T18:12:39.670Z"
    },
    "searchTerms": [
      {
        "searchTermId": "zr9vMtv0MBbtng8KTglh",
        "query": "Která banka nabízí nejlepší výhody pro mladé klienty?",
        "aiSearchEngines": ["google_ai_mode_gui"],
        "topic": {
          "id": "ZFyMrgG0cuuEAvCdf1nr",
          "name": "Brand"
        },
        "tags": [],
        "status": "active",
        "interval": "weekly",
        "region": "cz",
        "websearch": true,
        "lastSnapshotAt": "2026-04-21T06:05:46.608Z",
        "ownBrand": {
          "name": "Česká spořitelna",
          "appearances": 1,
          "avgRank": 7,
          "isOwnBrand": true,
          "latestRank": null,
          "detectionRate": 50,
          "top3": 0,
          "citationCount": 1,
          "avgSentiment": 70,
          "firstSeen": "2026-04-14T06:17:35.108Z",
          "lastSeen": "2026-04-14T06:17:35.108Z",
          "visibilityScore": 31.3,
          "variations": []
        },
        "competitors": [
          {
            "name": "ČSOB",
            "appearances": 2,
            "avgRank": 1,
            "isOwnBrand": false,
            "latestRank": 1,
            "detectionRate": 100,
            "top3": 100,
            "citationCount": 0,
            "avgSentiment": 72.5,
            "firstSeen": "2026-04-14T06:17:35.108Z",
            "lastSeen": "2026-04-21T06:05:41.494Z",
            "visibilityScore": 100,
            "variations": []
          },
          {
            "name": "MONETA Money Bank",
            "appearances": 2,
            "avgRank": 3.5,
            "isOwnBrand": false,
            "latestRank": 3,
            "detectionRate": 100,
            "top3": 50,
            "citationCount": 2,
            "avgSentiment": 80,
            "firstSeen": "2026-04-14T06:17:35.108Z",
            "lastSeen": "2026-04-21T06:05:41.494Z",
            "visibilityScore": 80,
            "variations": [
              {
                "name": "MONETA Money Bank",
                "appearances": 1,
                "avgRank": 3,
                "isOwnBrand": false,
                "latestRank": 3,
                "detectionRate": 50,
                "top3": 50,
                "citationCount": 1,
                "avgSentiment": 80,
                "firstSeen": "2026-04-21T06:05:41.494Z",
                "lastSeen": "2026-04-21T06:05:41.494Z",
                "visibilityScore": 41.7,
                "variations": []
              }
            ]
          }
        ]
      }
    ]
  }
}
```

#### Pole response

**`data{}`** – kořen

| Pole | Typ | Popis |
|---|---|---|
| `timeFrame` | string | Použité časové okno, např. `"7d"` |
| `requestedDateRange.source` | string | `"timeFrame"` nebo `"custom"` |
| `requestedDateRange.startDate` | timestamp | Začátek období |
| `requestedDateRange.endDate` | timestamp | Konec období |

**`data.searchTerms[]`** – jeden záznam per search term

| Pole | Typ | Popis |
|---|---|---|
| `searchTermId` | string | Unikátní ID search termu |
| `query` | string | Znění promptu |
| `aiSearchEngines` | array | Enginy na kterých tento search term běží, např. `["google_ai_mode_gui"]` |
| `topic.id` | string | ID topicu |
| `topic.name` | string | Název topicu |
| `tags` | array | Pole tagů, může být prázdné `[]` |
| `status` | string | `"active"` nebo `"inactive"` |
| `interval` | string | Frekvence: `"weekly"`, `"daily"` |
| `region` | string | Region, např. `"cz"` |
| `websearch` | boolean | Zda engine používá webové vyhledávání |
| `lastSnapshotAt` | timestamp | Kdy byl naposledy spuštěn snapshot |
| `ownBrand` | object \| undefined | Metriky vlastního brandu – **chybí** pokud se brand v daném search termu neobjevil |
| `competitors` | array | Pole konkurentů detekovaných v tomto search termu |

**`ownBrand{}`** – agregované metriky vlastního brandu za dané období

> ⚠️ Pole `ownBrand` je **volitelné** – chybí úplně pokud vlastní brand nebyl detekován v žádném snapshotu daného search termu.

| Pole | Typ | Popis |
|---|---|---|
| `name` | string | Název brandu |
| `appearances` | integer | Počet snapshotů kde se brand objevil |
| `avgRank` | float | Průměrná pozice za dané období |
| `isOwnBrand` | boolean | Vždy `true` u vlastního brandu |
| `latestRank` | integer \| null | Pozice v posledním snapshotu (`null` = v posledním kole nenalezen) |
| `detectionRate` | float | % snapshotů kde se brand objevil (0–100) |
| `top3` | float | % výskytů na pozici 1–3 (0–100) |
| `citationCount` | integer | Celkový počet citací |
| `avgSentiment` | float | Průměrný sentiment (**0–100**, ne 0–1!) |
| `firstSeen` | timestamp | První detekce v daném období |
| `lastSeen` | timestamp | Poslední detekce v daném období |
| `visibilityScore` | float | Visibility skóre (0–100) |
| `variations` | array | Varianty názvu brandu (obvykle prázdné u `ownBrand`) |

**`competitors[]`** – jeden objekt per konkurent, stejná struktura jako `ownBrand`

| Pole | Typ | Popis |
|---|---|---|
| `name` | string | Kanonický název konkurenta |
| `appearances` | integer | Počet snapshotů kde se konkurent objevil |
| `avgRank` | float | Průměrná pozice za dané období |
| `isOwnBrand` | boolean | Vždy `false` u konkurentů |
| `latestRank` | integer \| null | Pozice v posledním snapshotu (`null` = v posledním kole nenalezen) |
| `detectionRate` | float | % snapshotů kde se brand objevil (0–100) |
| `top3` | float | % výskytů na pozici 1–3 (0–100) |
| `citationCount` | integer | Celkový počet citací |
| `avgSentiment` | float | Průměrný sentiment (**0–100**) |
| `firstSeen` | timestamp | První detekce v daném období |
| `lastSeen` | timestamp | Poslední detekce v daném období |
| `visibilityScore` | float | Visibility skóre (0–100) |
| `variations` | array | Varianty názvu detekované AI – viz níže |

**`competitors[].variations[]`** – varianty názvu stejného brandu

Rankscale detekuje různé varianty zápisu jednoho brandu (např. `"MONETA Money Bank"`, `"Moneta Money Bank"`, `"MONETA"`). Každá varianta má stejnou strukturu jako parent objekt, ale s vlastními metrikami. Pole `variations` je rekurzivní ale **vnořené varianty mají vždy prázdné `variations: []`**.

| Pole | Popis |
|---|---|
| `name` | Konkrétní varianta zápisu |
| `appearances` | Počet výskytů této konkrétní varianty |
| `avgRank`, `latestRank`, atd. | Metriky specifické pro tuto variantu |
| `variations` | Vždy `[]` (žádné další zanoření) |

#### Co se liší oproti oficiální dokumentaci

| Oficiální dokumentace | Realita |
|---|---|
| `topic` je string | `topic` je **objekt** `{ id: string, name: string }` |
| `latestRun{}` s metrikami posledního běhu | **Neexistuje** – místo toho jsou na search termu agregované `ownBrand{}` a `competitors[]` |
| `trend{}` s direction a change | **Neexistuje** |
| `answerTexts[]` s raw texty | **Neexistuje** (nebo nepotvrzeno) |
| `includeAnswerTexts` parametr | **Nepotvrzeno** |
| Sentiment na škále 0–1 | Sentiment na škále **0–100** |
| `data.timeFrame` neexistuje | `data.timeFrame` existuje (echo použitého parametru) |
| Žádné info o statusu/enginu/regionu search termu | `status`, `aiSearchEngines`, `interval`, `region`, `websearch`, `lastSnapshotAt` jsou součástí každého záznamu |
| `ownBrand` neexistuje | `ownBrand{}` je samostatné pole oddělené od `competitors[]` |
| Žádné `variations[]` | Každý brand/competitor má `variations[]` s variantami názvů |

---

### POST /v1/metrics/sentiment

Sentiment data – jak pozitivně/negativně AI enginy hovoří o brandě.

> ⏳ **Čeká na ověření reálným API response.**

#### Request

```http
POST /v1/metrics/sentiment
Authorization: Bearer rk_your_api_key_here
Content-Type: application/json
```

```json
{
  "brandId": "brand_abc123",
  "timeFrame": "30d",
  "periodOffset": 0,
  "selectedTopic": "all",
  "selectedEngine": "all",
  "selectedQuery": "all"
}
```

#### Tělo requestu

| Pole | Typ | Povinný | Popis |
|---|---|---|---|
| `brandId` | string | ✅ | ID brandy |
| `timeFrame` | string | | Časové okno |
| `periodOffset` | integer | | Posun o N period |
| `selectedTopic` | string | | Filtr topicu nebo `"all"` |
| `selectedEngine` | string\|array | | Filtr enginů nebo `"all"` |
| `selectedQuery` | string | | Filtr search termu nebo `"all"` |
| `isoStartDate` | string | | Vlastní začátek |
| `isoEndDate` | string | | Vlastní konec |

#### Response

```json
{
  "success": true,
  "data": {
    "overall": {
      "score": 0.72,
      "label": "positive",
      "distribution": {
        "positive": 0.65,
        "neutral": 0.25,
        "negative": 0.10
      }
    },
    "byEngine": {
      "chatgpt": { "score": 0.78, "label": "positive" },
      "gemini": { "score": 0.65, "label": "positive" },
      "perplexity": { "score": 0.73, "label": "positive" }
    },
    "timeSeries": [
      {
        "date": "2026-03-15T00:00:00.000Z",
        "score": 0.70,
        "positive": 0.63,
        "neutral": 0.27,
        "negative": 0.10
      }
    ]
  }
}
```

#### Pole response

**`data.overall{}`**

| Pole | Typ | Popis |
|---|---|---|
| `score` | float | Celkový sentiment (**0–1**) |
| `label` | string | `"positive"`, `"neutral"`, nebo `"negative"` |
| `distribution.positive` | float | Podíl pozitivních zmínek (**0–1**, ne %) |
| `distribution.neutral` | float | Podíl neutrálních zmínek |
| `distribution.negative` | float | Podíl negativních zmínek |

**`data.byEngine{}`** – klíč je název enginu

| Pole | Typ | Popis |
|---|---|---|
| `[engine].score` | float | Sentiment score (0–1) |
| `[engine].label` | string | `"positive"`, `"neutral"`, `"negative"` |

**`data.timeSeries[]`** – jeden záznam per agregační period

| Pole | Typ | Popis |
|---|---|---|
| `date` | timestamp | Datum periody |
| `score` | float | Sentiment score (0–1) |
| `positive` | float | Podíl pozitivních (0–1) |
| `neutral` | float | Podíl neutrálních (0–1) |
| `negative` | float | Podíl negativních (0–1) |

> ⚠️ Všechny hodnoty jsou **float 0–1**, ne procenta. `positive + neutral + negative ≈ 1.0`.

---

### POST /v1/metrics/citations

Domény a URL které AI enginy citují jako zdroje při odpovídání na sledované search terms.

> ⏳ **Čeká na ověření reálným API response.**

#### Request

```http
POST /v1/metrics/citations
Authorization: Bearer rk_your_api_key_here
Content-Type: application/json
```

```json
{
  "brandId": "brand_abc123",
  "timeFrame": "30d",
  "periodOffset": 0,
  "selectedTopic": "all",
  "selectedEngine": "all",
  "selectedQuery": "all"
}
```

#### Tělo requestu

| Pole | Typ | Povinný | Popis |
|---|---|---|---|
| `brandId` | string | ✅ | ID brandy |
| `timeFrame` | string | | Časové okno |
| `periodOffset` | integer | | Posun o N period |
| `selectedTopic` | string | | Filtr topicu nebo `"all"` |
| `selectedEngine` | string\|array | | Filtr enginů nebo `"all"` |
| `selectedQuery` | string | | Filtr search termu nebo `"all"` |
| `limit` | integer | | Max záznamů per stránka (výchozí 50) |
| `offset` | integer | | Offset pro stránkování |
| `isoStartDate` | string | | Vlastní začátek |
| `isoEndDate` | string | | Vlastní konec |

#### Response

```json
{
  "success": true,
  "data": {
    "citations": [
      {
        "url": "https://collectorboy.cz/hot-toys-recenze",
        "title": "Hot Toys recenze 2025 – CollectorBoy",
        "domain": "collectorboy.cz",
        "engine": "perplexity",
        "searchTermId": "st_abc123",
        "query": "kde koupit Hot Toys figury v ČR",
        "firstSeen": "2026-03-10T12:00:00.000Z",
        "lastSeen": "2026-04-27T08:00:00.000Z",
        "count": 15
      }
    ],
    "summary": {
      "totalCitations": 156,
      "uniqueUrls": 42,
      "uniqueDomains": 18,
      "topDomains": [
        { "domain": "collectorboy.cz", "count": 24 },
        { "domain": "mall.cz", "count": 18 }
      ]
    },
    "pagination": {
      "total": 156,
      "limit": 50,
      "offset": 0,
      "hasMore": true
    }
  }
}
```

#### Pole response

**`data.citations[]`**

| Pole | Typ | Popis |
|---|---|---|
| `url` | string | Citovaná URL |
| `title` | string | Titulek stránky |
| `domain` | string | Doména |
| `engine` | string | Engine kde se citace objevila |
| `searchTermId` | string | ID search termu ke kterému se váže |
| `query` | string | Znění search termu |
| `firstSeen` | timestamp | Kdy byla citace poprvé zaznamenána |
| `lastSeen` | timestamp | Kdy byla naposledy viděna |
| `count` | integer | Celkový počet výskytů |

**`data.summary{}`**

| Pole | Typ | Popis |
|---|---|---|
| `totalCitations` | integer | Celkový počet citací |
| `uniqueUrls` | integer | Počet unikátních URL |
| `uniqueDomains` | integer | Počet unikátních domén |
| `topDomains[]` | array | Nejcitovanější domény: `{ domain, count }` |

**`data.pagination{}`**

| Pole | Typ | Popis |
|---|---|---|
| `total` | integer | Celkový počet záznamů |
| `limit` | integer | Počet záznamů na stránce |
| `offset` | integer | Aktuální offset |
| `hasMore` | boolean | Existuje další stránka? |

#### Stránkování

```http
# Stránka 1 (výchozí)
POST /v1/metrics/citations
{ "brandId": "...", "limit": 50, "offset": 0 }

# Stránka 2
POST /v1/metrics/citations
{ "brandId": "...", "limit": 50, "offset": 50 }

# Opakuj dokud hasMore = false
```

---

## Chybové kódy

| HTTP status | Kód | Popis |
|---|---|---|
| `200` | – | Úspěch |
| `400` | `BAD_REQUEST` | Chybějící nebo neplatné parametry |
| `401` | `UNAUTHORIZED` | Neplatný nebo chybějící API klíč |
| `403` | `FORBIDDEN` | API přístup není povolen pro váš plán |
| `404` | `NOT_FOUND` | Zdroj neexistuje |
| `422` | `VALIDATION_ERROR` | Validace selhala |
| `429` | `RATE_LIMIT_EXCEEDED` | Překročen rate limit (200 req/min) |
| `500` | `INTERNAL_ERROR` | Neočekávaná chyba na serveru |

---

## Zjištěné odchylky API vs dokumentace

| Dokumentace říká | Realita |
|---|---|
| `searchTerms[].brandId` | Pole **neexistuje** v response – použij `brandId` z parametru volání |
| `searchTerms[].query` | Název pole se může lišit – ověř debug logem |