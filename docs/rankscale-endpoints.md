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
| `POST /v1/metrics/sentiment` | ✅ Ověřeno | Reálný response k dispozici |
| `POST /v1/metrics/citations` | ✅ Ověřeno | Reálný response k dispozici |
| `GET /v1/metrics/credits` | ✅ Ověřeno | Reálný response k dispozici |
| `GET /v1/metrics/topics` | ✅ Ověřeno | Reálný response k dispozici |

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
  - [GET /v1/metrics/credits](#get-v1metricscredits)
  - [GET /v1/metrics/topics](#get-v1metricstopics)
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

Jeden objekt per brand. **Zahrnuje i vlastní brand** jako první prvek (s `isOwnBrand: true`) – pole tedy není čistě "konkurence", ale celkový přehled všech brandů včetně vlastního.

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

Má stejné 4 klíče jako ostatní timeseries. Neobsazené úrovně mají `timestamps: []` a `competitors: []`. Aktivní úroveň má `timestamps` sdílené pro všechny konkurenty a pole `competitors[]` kde každý má `metrics{}` s paralelními poli.

> ⚠️ **Vlastní brand v `competitorTimeSeriesData` chybí** – timeseries vlastního brandu je v `ownBrandMetrics.historicalData`.

```json
{
  "hourly": { "timestamps": [], "competitors": [] },
  "daily": {
    "timestamps": ["2026-04-07T00:00:00.000Z", "2026-04-14T00:00:00.000Z", "2026-04-21T00:00:00.000Z"],
    "competitors": [
      {
        "name": "Air Bank",
        "isOwnBrand": false,
        "variations": ["Air Bank"],
        "metrics": {
          "visibilityScore": [60.6, 60.8, 59.5],
          "sentiment":       [67.8, 68.4, 67.7],
          "avgPosition":     [3.2, 3.1, 3.2],
          "detectionRate":   [71.3, 71.7, 70.4],
          "top3":            [45.4, 45, 45.4],
          "mentions":        [181, 176, 175],
          "citations":       [152, 100, 105]
        }
      }
    ]
  },
  "weekly":  { "timestamps": [], "competitors": [] },
  "monthly": { "timestamps": [], "competitors": [] }
}
```

#### Co se liší oproti oficiální dokumentaci

| Oficiální dokumentace | Realita |
|---|---|
| `data.summary{}` | Metriky přímo na `data.ownBrandMetrics{}` |
| `data.timeSeries[]` – pole objektů | `historicalData.daily{}` – paralelní pole hodnot |
| `data.byEngine{}` – klíče jako engine ID | `engineMetricsData.daily[]` – pole objektů |
| Endpoint vrací jen vlastní brand | Vrací **vlastní brand + konkurenci + timeseries** vše najednou |
| `sentiment` je 0–1 float | `sentiment` je **0–100** (např. `62.5`) |
| Bez `brandNotFound` | `brandNotFound[]` – paralelní boolean pole; `false` = 100% detection v bucketu, `true` = alespoň jeden snapshot brand nenašel |
| Bez `topicMetricsData` | Topic breakdown je součástí response |
| Bez `competitorMetrics` | Konkurence je součástí response |
| Bez `preselectionWhitelist/Blacklist` | Whitelist/blacklist je uvnitř `ownBrandMetrics`, ne samostatný klíč |
| Bez `variations[]` | Každý brand má pole variant názvů |
| `competitorMetrics[]` = jen konkurenti | **Zahrnuje i vlastní brand** jako první prvek (`isOwnBrand: true`) |
| `historicalData` jen jedna agregační úroveň | Vždy všechny 4 úrovně (`hourly`/`daily`/`weekly`/`monthly`); neobsazené jsou prázdná pole `[]` |
| `competitorTimeSeriesData` bez struktury | Má také 4 úrovně; vlastní brand zde **chybí** – je v `ownBrandMetrics.historicalData` |


---

### POST /v1/metrics/search-terms-report

Metriky rozpadnuté na úroveň každého jednotlivého search termu. Pro každý search term vrací agregované metriky vlastního brandu (`ownBrand`) a seznam konkurentů (`competitors`) za zvolené časové období.

> ✅ **Ověřeno reálným API response.**

> ⚠️ **Klíčová zjištění:**
> - Struktura je **zásadně jiná** než dokumentace uváděla – žádný `latestRun`, `trend`
> - Každý search term obsahuje `ownBrand{}` (volitelné – chybí pokud se brand neobjevil) a `competitors[]`
> - `topic` je **objekt** `{ id, name }`, ne string
> - Sentiment je na škále **0–100**, ne 0–1
> - `ownBrand` a každý competitor mají pole `variations[]` s variantami názvu (může být prázdné)
> - `answerTexts[]` existuje – obsahuje raw AI texty odpovědí, aktivuje se parametrem `includeAnswerTexts: true`

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
| `includeAnswerTexts` | boolean | | Pokud `true`, každý search term obsahuje `answerTexts[]` s texty AI odpovědí |

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
        ],
        "answerTexts": [
          {
            "executionId": "ILNvgH8ctdACeQMfTXta",
            "executedAt": "2026-05-19T06:07:49.313Z",
            "engine": "google_ai_mode_gui",
            "answerText": "**UniCredit Bank, Komerční banka a ČSOB** momentálně nabízejí..."
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
| `answerTexts` | array \| undefined | Raw AI odpovědi – přítomné jen pokud `includeAnswerTexts: true` v requestu |

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

**`answerTexts[]`** – raw AI odpovědi per search term (jen pokud `includeAnswerTexts: true`)

| Pole | Typ | Popis |
|---|---|---|
| `executionId` | string | ID konkrétní exekuce snapshotu |
| `executedAt` | timestamp | Kdy byla exekuce provedena |
| `engine` | string | Engine ID, např. `"google_ai_mode_gui"` |
| `answerText` | string | Plný text AI odpovědi (markdown, může obsahovat tabulky a citační linky) |

> `answerTexts[]` obsahuje typicky 1–2 záznamy per search term (poslední snapshot per engine). Každý záznam je vždy z jiného `executionId`.

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
| `answerTexts[]` s raw texty | **Existuje** – aktivuje se `includeAnswerTexts: true` v requestu |
| `includeAnswerTexts` parametr | **Existuje** – volitelný boolean parametr |
| Sentiment na škále 0–1 | Sentiment na škále **0–100** |
| `data.timeFrame` neexistuje | `data.timeFrame` existuje (echo použitého parametru) |
| Žádné info o statusu/enginu/regionu search termu | `status`, `aiSearchEngines`, `interval`, `region`, `websearch`, `lastSnapshotAt` jsou součástí každého záznamu |
| `ownBrand` neexistuje | `ownBrand{}` je samostatné pole oddělené od `competitors[]` |
| Žádné `variations[]` | Každý brand/competitor má `variations[]` s variantami názvů |

---

### POST /v1/metrics/sentiment

Vrací seznam brandů s rozpadem sentimentu na konkrétní pozitivní a negativní klíčová slova detekovaná v AI odpovědích.

> ✅ **Ověřeno reálným API response.**

> ⚠️ **Klíčová zjištění:**
> - Struktura je **zásadně jiná** než dokumentace uváděla – žádné `overall`, `byEngine`, `timeSeries`
> - Response vrací **pole brandů** (`brandSentiments[]`), každý s hrubým skóre a keyword slovníky
> - `totalSentimentScore` je **raw součet** (ne průměr) – průměr = `totalSentimentScore / sentimentCount` (škála 0–100)
> - `avgSentiment` je pre-vypočítaný float přímo na objektu (float, škála 0–100)
> - Klíčová slova jsou jako **objekt se stringovými klíči** (text klíčového slova), ne pole
> - Každé klíčové slovo má `{count, executionIds[], timestamps[]}` – `executionIds` a `timestamps` jsou paralelní pole
> - Vedle `positiveKeywords` existují také `neutralKeywords{}` a `negativeKeywords{}` – stejná struktura
> - `webGroundingKeywords{}` a `trainingDataKeywords{}` rozkládají klíčová slova dle zdroje AI (webové vyhledávání vs. trénovací data)
> - `webGroundingSentimentByEngine{}` a `trainingDataSentimentByEngine{}` dávají breakdown sentimentu per engine dle zdroje

#### Request

```http
POST /v1/metrics/sentiment
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
| `selectedEngine` | string\|array | | Filtr enginů nebo `"all"` |
| `selectedQuery` | string | | Filtr search termu nebo `"all"` |
| `isoStartDate` | string | | Vlastní začátek (přepíše `timeFrame`) |
| `isoEndDate` | string | | Vlastní konec (přepíše `timeFrame`) |

#### Response

```json
{
  "success": true,
  "data": {
    "brandSentiments": [
      {
        "name": "Ceska sporitelna",
        "totalSentimentScore": 12810,
        "sentimentCount": 181,
        "executionCount": 181,
        "isOwnBrand": true,
        "avgSentiment": 70.77,
        "positiveCount": 331,
        "neutralCount": 155,
        "negativeCount": 64,
        "hasWebGrounding": true,
        "hasTrainingData": false,
        "nameVariations": ["Česká spořitelna", "Spořitelna"],
        "positiveKeywords": {
          "stabilita": {
            "count": 3,
            "executionIds": ["QCns3PgAiQMdvPEyZc2L", "ZOgU43J8WzvkPoayAQgD"],
            "timestamps": ["2026-05-19T06:08:02.769Z", "2026-05-19T06:08:46.467Z"]
          },
          "aplikace george": {
            "count": 10,
            "executionIds": ["mdcka2OihRSrunpmG7je", "..."],
            "timestamps": ["2026-05-19T06:07:58.497Z", "..."]
          }
        },
        "neutralKeywords": {
          "půjčka na cokoliv": {
            "count": 1,
            "executionIds": ["DJVUKnS726RvDiiR7nqC"],
            "timestamps": ["2026-05-19T06:06:57.815Z"]
          }
        },
        "negativeKeywords": {
          "vysoké poplatky": {
            "count": 2,
            "executionIds": ["abc123", "def456"],
            "timestamps": ["2026-05-19T06:08:10.000Z", "2026-05-19T06:09:00.000Z"]
          }
        },
        "webGroundingKeywords": {
          "positive": {
            "možností odkladu splátek": {
              "count": 1,
              "executionIds": ["DJVUKnS726RvDiiR7nqC"],
              "timestamps": ["2026-05-19T06:06:57.815Z"]
            }
          },
          "neutral": {
            "půjčka na cokoliv": {
              "count": 1,
              "executionIds": ["DJVUKnS726RvDiiR7nqC"],
              "timestamps": ["2026-05-19T06:06:57.815Z"]
            }
          },
          "negative": {
            "poplatky za sjednání": {
              "count": 1,
              "executionIds": ["YWC7abUuV6Qm68UVGF0v"],
              "timestamps": ["2026-05-19T06:07:48.315Z"]
            }
          },
          "byEngine": {
            "google_ai_overview": {
              "positive": { "možností odkladu splátek": { "count": 1, "executionIds": ["..."], "timestamps": ["..."] } },
              "neutral": { "půjčka na cokoliv": { "count": 1, "executionIds": ["..."], "timestamps": ["..."] } },
              "negative": { "3 až 8 týdnů": { "count": 1, "executionIds": ["..."], "timestamps": ["..."] } }
            }
          }
        },
        "trainingDataKeywords": {
          "positive": {},
          "neutral": {},
          "negative": {},
          "byEngine": {}
        },
        "webGroundingSentimentByEngine": {
          "google_ai_overview": { "sum": 2231, "count": 31, "avg": 71.97 },
          "google_ai_mode_gui": { "sum": 4580, "count": 65, "avg": 70.46 }
        },
        "trainingDataSentimentByEngine": {}
      }
    ]
  }
}
```

#### Pole response

**`data.brandSentiments[]`** – jeden objekt per brand

| Pole | Typ | Popis |
|---|---|---|
| `name` | string | Název brandu (**bez diakritiky** – `"Ceska sporitelna"`, ne `"Česká spořitelna"`) |
| `totalSentimentScore` | integer | Raw součet všech sentiment skóre za dané období |
| `sentimentCount` | integer | Počet sentiment měření (zmínek) |
| `executionCount` | integer | Počet exekucí zahrnutých v analýze |
| `isOwnBrand` | boolean | `true` pokud jde o vlastní brand |
| `avgSentiment` | float | Pre-vypočítaný průměrný sentiment (**0–100**) – ekvivalent `totalSentimentScore / sentimentCount` |
| `positiveCount` | integer | Počet unikátních pozitivních klíčových slov |
| `neutralCount` | integer | Počet unikátních neutrálních klíčových slov |
| `negativeCount` | integer | Počet unikátních negativních klíčových slov |
| `hasWebGrounding` | boolean | Zda AI engine pro tento brand používal webové zdroje (web grounding) |
| `hasTrainingData` | boolean | Zda AI engine použil trénovací data (bez webového vyhledávání) |
| `nameVariations` | array | Různé varianty názvu brandu detekované AI, např. `["Česká spořitelna", "Spořitelna"]` |
| `positiveKeywords` | object | Slovník pozitivních klíčových slov – viz níže |
| `neutralKeywords` | object | Slovník neutrálních klíčových slov – stejná struktura jako `positiveKeywords` |
| `negativeKeywords` | object | Slovník negativních klíčových slov – stejná struktura |
| `webGroundingKeywords` | object | Klíčová slova roztříděná dle zdroje: webové vyhledávání – viz níže |
| `trainingDataKeywords` | object | Klíčová slova z trénovacích dat AI – stejná struktura jako `webGroundingKeywords` |
| `webGroundingSentimentByEngine` | object | Breakdown sentimentu z webových zdrojů per engine – viz níže |
| `trainingDataSentimentByEngine` | object | Breakdown sentimentu z trénovacích dat per engine – prázdné pokud `hasTrainingData: false` |

> **Výpočet průměrného sentimentu:** `avgSentiment = totalSentimentScore / sentimentCount` → výsledek je na škále **0–100** (shoduje se s `avgSentiment` v ostatních endpointech). Pole `avgSentiment` je pre-vypočítaný float přímo v response.

**`positiveKeywords{}` / `neutralKeywords{}` / `negativeKeywords{}`** – klíč je text klíčového slova

Klíčová slova jsou **objekt, ne pole**. Každý klíč je string s textem klíčového slova (v jazyce search termu).

| Pole | Typ | Popis |
|---|---|---|
| `[keyword].count` | integer | Celkový počet výskytů tohoto klíčového slova |
| `[keyword].executionIds` | array | ID jednotlivých exekucí kde bylo slovo detekováno |
| `[keyword].timestamps` | array | Timestampy exekucí – **paralelní pole** k `executionIds` |

> ⚠️ `executionIds` a `timestamps` jsou paralelní pole – index 0 v `executionIds` odpovídá indexu 0 v `timestamps`.

> ⚠️ `count` nemusí odpovídat délce `executionIds` – jedno ID execution se může v poli opakovat vícekrát (keyword byl detekován vícekrát v rámci jedné exekuce).

**`webGroundingKeywords{}`** – klíčová slova z webových zdrojů (a `trainingDataKeywords{}` analogicky)

Objekt má 4 sub-klíče:

| Sub-klíč | Typ | Popis |
|---|---|---|
| `positive` | object | Pozitivní klíčová slova z webového vyhledávání – stejná struktura jako `positiveKeywords` |
| `neutral` | object | Neutrální klíčová slova |
| `negative` | object | Negativní klíčová slova |
| `byEngine` | object | Breakdown per engine – klíč je engine ID, hodnota má sub-klíče `positive`, `neutral`, `negative` se stejnou keyword strukturou |

**`webGroundingSentimentByEngine{}`** – sentiment z webových zdrojů per engine

Objekt je keyed by engine ID, každá hodnota:

| Pole | Typ | Popis |
|---|---|---|
| `sum` | integer | Součet sentiment skóre z webových zdrojů pro tento engine |
| `count` | integer | Počet měření |
| `avg` | float | Průměrný sentiment pro tento engine (**0–100**) |

#### Co se liší oproti oficiální dokumentaci

| Oficiální dokumentace | Realita |
|---|---|
| `data.overall.score` (float 0–1) | **Neexistuje** |
| `data.overall.label` (`"positive"` apod.) | **Neexistuje** |
| `data.overall.distribution` | **Neexistuje** |
| `data.byEngine{}` | **Neexistuje** |
| `data.timeSeries[]` | **Neexistuje** |
| Sentiment na škále 0–1 | `totalSentimentScore` je raw součet; průměr je na škále **0–100** |
| Bez keyword breakdown | `positiveKeywords{}`, `neutralKeywords{}`, `negativeKeywords{}` + web/trainingData varianty |
| Jeden souhrnný objekt | `brandSentiments[]` – **pole brandů** |
| Název brandu s diakritikou | Název **bez diakritiky** (ASCII verze) |
| Bez breakdown dle zdroje | `webGroundingKeywords{}` a `trainingDataKeywords{}` rozdělují klíčová slova dle zdroje AI |
| Bez engine breakdown sentimentu | `webGroundingSentimentByEngine{}` a `trainingDataSentimentByEngine{}` |
| Bez pre-count polí | `positiveCount`, `neutralCount`, `negativeCount` – počty unikátních klíčových slov per kategorie |
| Bez `nameVariations` | `nameVariations[]` – detekované varianty jména brandu |
| Bez `executionCount`, `isOwnBrand` | `executionCount` a `isOwnBrand` jsou součástí každého záznamu |

---

### POST /v1/metrics/citations

Domény a URL které AI enginy citují jako zdroje při odpovídání na sledované search terms. Vrací souhrnný přehled nejcitovanějších domén a URL s počty výskytů.

> ✅ **Ověřeno reálným API response.**

> ⚠️ **Klíčová zjištění:**
> - Struktura je **zásadně jiná** než dokumentace uváděla – žádné `citations[]`, `summary{}` ani `pagination{}`
> - Souhrnné čítače jsou přímo na `data{}`, ne zanořené
> - `paginationInfo{}` je mnohem detailnější objekt s cap limity
> - `domainSummary.topDomainsOverall[]` je hlavní datová část – každá doména má vnořené `urls[]`
> - Endpoint vrací **agregovaný přehled domén**, ne seznam jednotlivých citací s metadaty

#### Request

```http
POST /v1/metrics/citations
Authorization: Bearer rk_your_api_key_here
Content-Type: application/json
```

```json
{
  "brandId": "E5GAVmqco65u7Smx3hso",
  "timeFrame": "30d"
}
```

#### Tělo requestu

| Pole | Typ | Povinný | Popis |
|---|---|---|---|
| `brandId` | string | ✅ | ID brandy |
| `timeFrame` | string | | Časové okno: `24h`, `7d`, `30d`, `3m`, `1y` |
| `periodOffset` | integer | | Posun o N period |
| `selectedTopic` | string | | Filtr topicu nebo `"all"` |
| `selectedEngine` | string\|array | | Filtr enginů nebo `"all"` |
| `selectedQuery` | string | | Filtr search termu nebo `"all"` |
| `isoStartDate` | string | | Vlastní začátek (přepíše `timeFrame`) |
| `isoEndDate` | string | | Vlastní konec (přepíše `timeFrame`) |

#### Response

```json
{
  "success": true,
  "data": {
    "totalCitations": 7058,
    "uniqueCitations": 2180,
    "uniqueDomains": 534,
    "totalBrands": 24,
    "timestampFormat": "daily",
    "paginationInfo": {
      "hasMore": false,
      "totalCount": 2180,
      "returnedCount": 2180,
      "citationsCapped": false,
      "brandsCapped": false,
      "capBypassed": false,
      "maxCitations": 5000,
      "maxBrands": 50,
      "responseTrimmed": false,
      "returnedDomainCount": 534,
      "totalDomainCount": 534
    },
    "domainSummary": {
      "topDomainsOverall": [
        {
          "domain": "banky.cz",
          "occurrences": 772,
          "urls": [
            { "url": "https://www.banky.cz/hypoteka", "occurrences": 31 },
            { "url": "https://www.banky.cz/prehled-a-porovnani/hypoteky-na-bydleni", "occurrences": 32 }
          ]
        }
      ],
      "topDomainsByEngine": [
        {
          "engineId": "bing_copilot_gui",
          "domains": [
            { "domain": "banky.cz", "occurrences": 69, "urls": [{ "url": "https://...", "occurrences": 10 }] }
          ]
        }
      ],
      "topDomainsByQuery": [
        {
          "query": "Která banka nabízí nejlepší výhody pro mladé klienty?",
          "searchTermIds": ["zr9vMtv0MBbtng8KTglh"],
          "engines": [
            {
              "engineId": "bing_copilot_gui",
              "domains": [{ "domain": "csas.cz", "occurrences": 4, "urls": [{ "url": "https://...", "occurrences": 4 }] }]
            }
          ]
        }
      ],
      "topDomainsByOwnBrandCitations": [
        {
          "domain": "csas.cz",
          "occurrences": 143,
          "urls": [{ "url": "https://www.csas.cz/cs/osobni-finance/pujcky/pujcka", "occurrences": 22 }]
        }
      ],
      "topDomainsByCompetitor": [
        {
          "brandName": "Air Bank",
          "occurrences": 606,
          "domains": [
            { "domain": "airbank.cz", "occurrences": 205, "urls": [{ "url": "https://www.airbank.cz/produkty/pujcka", "occurrences": 37 }] }
          ]
        }
      ]
    },
    "citationsByDomain": [
      {
        "domain": "banky.cz",
        "occurrences": 772,
        "citations": ["..."]
      }
    ]
  }
}
```

#### Pole response

**`data{}`** – kořenové souhrnné čítače

| Pole | Typ | Popis |
|---|---|---|
| `totalCitations` | integer | Celkový počet citací (včetně duplicit) |
| `uniqueCitations` | integer | Počet unikátních URL citací |
| `uniqueDomains` | integer | Počet unikátních domén |
| `totalBrands` | integer | Počet brandů zahrnutých v response |
| `timestampFormat` | string | Granularita časových dat, např. `"daily"` |

**`data.paginationInfo{}`** – informace o limitech a stránkování

| Pole | Typ | Popis |
|---|---|---|
| `hasMore` | boolean | Existují další stránky? |
| `totalCount` | integer | Celkový počet unikátních citací |
| `returnedCount` | integer | Počet vrácených citací v tomto response |
| `citationsCapped` | boolean | Byl response oříznut limitem `maxCitations`? |
| `brandsCapped` | boolean | Byl response oříznut limitem `maxBrands`? |
| `capBypassed` | boolean | Byl cap limit obejit (např. admin přístupem)? |
| `maxCitations` | integer | Maximální počet citací v response (výchozí 5000) |
| `maxBrands` | integer | Maximální počet brandů v response (výchozí 50) |
| `responseTrimmed` | boolean | Byl response celkově oříznut? |
| `returnedDomainCount` | integer | Počet vrácených domén |
| `totalDomainCount` | integer | Celkový počet unikátních domén |

**`data.domainSummary{}`** – přehledy domén z různých úhlů pohledu

`domainSummary` obsahuje 5 sub-klíčů:

| Sub-klíč | Počet položek | Popis |
|---|---|---|
| `topDomainsOverall[]` | max 20 | Top domény celkově dle `occurrences` |
| `topDomainsByEngine[]` | per engine | Top domény roztříděné dle engine |
| `topDomainsByQuery[]` | per search term | Top domény roztříděné dle query/search termu |
| `topDomainsByOwnBrandCitations[]` | max 20 | Top domény specificky pro citace vlastního brandu |
| `topDomainsByCompetitor[]` | max 10 | Top domény per competitor brand |

**`topDomainsOverall[]`** – stejná struktura jako `topDomainsByOwnBrandCitations[]`

| Pole | Typ | Popis |
|---|---|---|
| `domain` | string | Název domény, např. `"banky.cz"` |
| `occurrences` | integer | Celkový počet výskytů domény v AI citacích |
| `urls[]` | array | Nejcitovanější URL z této domény – viz níže |

**`urls[]`** – vnořené URL v rámci domény (uvnitř všech domainSummary polí)

| Pole | Typ | Popis |
|---|---|---|
| `url` | string | Plná URL citovaná AI enginy |
| `occurrences` | integer | Počet výskytů této konkrétní URL |

> `urls[]` jsou seřazeny sestupně dle `occurrences`.

**`topDomainsByEngine[]`** – domény per AI engine

| Pole | Typ | Popis |
|---|---|---|
| `engineId` | string | ID enginu, např. `"bing_copilot_gui"` |
| `domains[]` | array | Top domény pro tento engine – každá položka má `domain`, `occurrences`, `urls[]` |

**`topDomainsByQuery[]`** – domény per search term/query

| Pole | Typ | Popis |
|---|---|---|
| `query` | string | Text search termu |
| `searchTermIds` | array | Pole ID search termů s tímto znění (může být víc na různých enginech) |
| `engines[]` | array | Per engine breakdown – každá položka má `engineId`, `domains[]` se stejnou strukturou |

**`topDomainsByCompetitor[]`** – domény per competitor brand

| Pole | Typ | Popis |
|---|---|---|
| `brandName` | string | Název competitor brandu |
| `occurrences` | integer | Celkový počet citací tohoto brandu |
| `domains[]` | array | Domény citované v kontextu tohoto brandu – každá položka má `domain`, `occurrences`, `urls[]` |

**`data.citationsByDomain[]`** – podrobný seznam citací per doména (534 položek v ukázce)

| Pole | Typ | Popis |
|---|---|---|
| `domain` | string | Název domény |
| `occurrences` | integer | Celkový počet výskytů |
| `citations` | array | Podrobný seznam citací z této domény |

> `citationsByDomain[]` je výrazně detailnější než `domainSummary` – obsahuje všechny domény (ne jen top N), ale struktura `citations[]` pole nebyla blíže zkoumána.

#### Co se liší oproti oficiální dokumentaci

| Oficiální dokumentace | Realita |
|---|---|
| `data.citations[]` – pole jednotlivých citací s metadaty | **Neexistuje** – endpoint vrací agregát, ne seznam |
| `data.summary{}` | **Neexistuje** – souhrnné čítače jsou přímo na `data{}` |
| `data.pagination{}` (total, limit, offset, hasMore) | `data.paginationInfo{}` – zcela jiný objekt s cap limity |
| `data.summary.uniqueUrls` | `data.uniqueCitations` |
| `data.summary.topDomains[].count` | `topDomainsOverall[].occurrences` |
| Každá doména bez vnořených URL | `urls[]` – každá doména má pole nejcitovanějších URL |
| `title`, `engine`, `searchTermId`, `query`, `firstSeen`, `lastSeen` na citaci | **Neexistují** – endpoint nevrací detail per citace |
| Stránkování přes `limit`/`offset` | `paginationInfo.citationsCapped` / `maxCitations` – cap model, ne offset |
| `data.summary.totalCitations` | `data.totalCitations` přímo na kořenu |
| Bez `totalBrands` | `data.totalBrands` – počet brandů v response |
| Bez `timestampFormat` | `data.timestampFormat` – granularita (`"daily"`) |
| `domainSummary` pouze s `topDomains[]` | `domainSummary` má 5 sub-klíčů: `topDomainsOverall`, `topDomainsByEngine`, `topDomainsByQuery`, `topDomainsByOwnBrandCitations`, `topDomainsByCompetitor` |
| Bez `citationsByDomain` | `citationsByDomain[]` – kompletní seznam 534 domén s citacemi |

---

### GET /v1/metrics/credits

Vrací aktuální stav kreditů workspace a odhad runway (jak dlouho kredity vydrží na základě průměrné spotřeby).

> ✅ **Ověřeno reálným API response.**

> ⚠️ **Klíčová zjištění:**
> - Endpoint je **GET**, ne POST – nepřijímá `brandId` ani časové parametry
> - `nextBilling` je ve formátu Firestore Timestamp (`{ _seconds, _nanoseconds }`), ne ISO string
> - `runway.estimatedRunwayHours` je float – pro dny děl 24
> - `dashboardRunway.metrics.runwayDays` může být `null` pokud je runway omezena billingem, ne spotřebou

#### Request

```http
GET /v1/metrics/credits
Authorization: Bearer rk_your_api_key_here
```

#### Response

```json
{
  "success": true,
  "data": {
    "rankCredits": 5247,
    "bonusRankCredits": 0,
    "analysisCredits": 200,
    "promptResearchCredits": 10,
    "creditsInFlight": 0,
    "runway": {
      "estimatedRunwayHours": 126.15,
      "creditsPerHourAvg": 0.376,
      "totalCostForNextExecution": 63.25,
      "nextBilling": {
        "_seconds": 1779810185,
        "_nanoseconds": 0
      },
      "simulationLimitedByBilling": true,
      "simulationLimitedByHorizon": false,
      "breakdown": {
        "hourly": 0,
        "daily": 0,
        "weekly": 253,
        "monthly": 0
      }
    },
    "dashboardRunway": {
      "isRunwayWarning": false,
      "runwayDays": null,
      "daysUntilValidUntil": 6,
      "metrics": {
        "creditsPerDay": 9.04,
        "rankCredits": 5247,
        "bonusRankCredits": 0,
        "analysisCredits": 200,
        "promptResearchCredits": 10,
        "runwayDays": null,
        "daysUntilValidUntil": 6,
        "isRunwayWarning": false,
        "executionsPerHour": 1.51,
        "executionsPerDay": 36.14,
        "executionsPerWeek": 253,
        "executionsPerMonth": 1084.29,
        "breakdown": {
          "hourly": 0,
          "daily": 0,
          "weekly": 253,
          "monthly": 0
        },
        "simulationLimitedByBilling": true,
        "simulationLimitedByHorizon": false
      }
    }
  }
}
```

#### Pole response

**Kreditové zůstatky** – přímo na `data{}`

| Pole | Typ | Popis |
|---|---|---|
| `rankCredits` | integer | Aktuální počet rank kreditů |
| `bonusRankCredits` | integer | Bonusové rank kredity (nad rámec předplatného) |
| `analysisCredits` | integer | Analýzové kredity |
| `promptResearchCredits` | integer | Kredity pro prompt research |
| `creditsInFlight` | integer | Kredity aktuálně blokované probíhajícími exekucemi |

**`data.runway{}`** – odhad vytrvalosti kreditů

| Pole | Typ | Popis |
|---|---|---|
| `estimatedRunwayHours` | float | Odhadovaný počet hodin než dojdou kredity |
| `creditsPerHourAvg` | float | Průměrná spotřeba kreditů za hodinu |
| `totalCostForNextExecution` | float | Cena příští naplánované exekuce v kreditech |
| `nextBilling._seconds` | integer | Unix timestamp příštího billing cyklu (Firestore formát) |
| `nextBilling._nanoseconds` | integer | Nanosekundová část timestampu (obvykle `0`) |
| `simulationLimitedByBilling` | boolean | `true` = runway je omezena billing datem, ne spotřebou kreditů |
| `simulationLimitedByHorizon` | boolean | `true` = simulace dosáhla časového horizontu |
| `breakdown.hourly` | integer | Počet hodinových exekucí per periodu |
| `breakdown.daily` | integer | Počet denních exekucí per periodu |
| `breakdown.weekly` | integer | Počet týdenních exekucí per periodu |
| `breakdown.monthly` | integer | Počet měsíčních exekucí per periodu |

> ⚠️ `nextBilling` je Firestore Timestamp – pro převod na datum: `new Date(nextBilling._seconds * 1000)`

> ⚠️ Pokud je `simulationLimitedByBilling: true`, runway odpovídá době do příštího billing cyklu, ne reálné spotřebě – `runwayDays` bude `null`.

**`data.dashboardRunway{}`** – dashboard-level runway info

| Pole | Typ | Popis |
|---|---|---|
| `isRunwayWarning` | boolean | `true` = runway je kriticky nízká (zobrazit varování) |
| `runwayDays` | float \| null | Počet dní zbývajících kreditů; `null` pokud limitováno billingem |
| `daysUntilValidUntil` | integer | Počet dní do konce platnosti předplatného |

**`data.dashboardRunway.metrics{}`** – detailní metriky pro dashboard

| Pole | Typ | Popis |
|---|---|---|
| `creditsPerDay` | float | Průměrná denní spotřeba kreditů |
| `executionsPerHour` | float | Průměrný počet exekucí za hodinu |
| `executionsPerDay` | float | Průměrný počet exekucí za den |
| `executionsPerWeek` | float | Průměrný počet exekucí za týden |
| `executionsPerMonth` | float | Průměrný počet exekucí za měsíc |
| `breakdown{}` | object | Stejný formát jako `runway.breakdown` |
| `simulationLimitedByBilling` | boolean | Viz `runway.simulationLimitedByBilling` |
| `simulationLimitedByHorizon` | boolean | Viz `runway.simulationLimitedByHorizon` |

> `metrics{}` obsahuje duplicitní pole (`rankCredits`, `bonusRankCredits` atd.) – jsou totožné s hodnotami na `data{}`.

---

### GET /v1/metrics/topics

Vrátí seznam všech topiců pro danou brandy. Topicy jsou tematické skupiny pro organizaci search termů. Každý topic obsahuje pole `searchTermIds` – seznam ID search termů přiřazených k danému topicu.

> ✅ **Ověřeno reálným API response.**

> ⚠️ **Klíčová zjištění:**
> - Parametr se jmenuje `brandRef` (ne `brandId` jako u ostatních endpointů)
> - `createdAt` a `updatedAt` jsou Firestore Timestamp objekty (`{ _seconds, _nanoseconds }`)
> - `updatedAt` **nemusí být vždy přítomno** – topics bez přiřazených search termů ho mohou postrádat
> - `searchTermIds[]` obsahuje ID ve formátu z `GET /v1/metrics/search-terms` (pole `id`)
> - `keywords` je vždy prázdný string – pole se zatím nepoužívá

#### Request

```http
GET /v1/metrics/topics?brandRef=E5GAVmqco65u7Smx3hso
Authorization: Bearer rk_your_api_key_here
```

#### Query parametry

| Parametr | Typ | Povinný | Popis |
|---|---|---|---|
| `brandRef` | string | ✅ | ID brandy (stejná hodnota jako `brandId` u jiných endpointů) |

#### Response

```json
{
  "success": true,
  "data": {
    "topics": [
      {
        "id": "ZFyMrgG0cuuEAvCdf1nr",
        "name": "Brand",
        "description": "",
        "brandRef": "E5GAVmqco65u7Smx3hso",
        "myBrand": "Česká spořitelna",
        "createdAt": { "_seconds": 1769496543, "_nanoseconds": 580000000 },
        "updatedAt": { "_seconds": 1771403386, "_nanoseconds": 600000000 },
        "createdBy": "hwSqTrrKF1ZaC98LamviUz9Bvqw1",
        "searchTermIds": ["xS7FDRiCviDIlTtUg80f", "a4pXbk0OMnHGvZrWlBUi"],
        "keywords": ""
      },
      {
        "id": "A4tgfyAXO2ekw5L64DNY",
        "name": "Hypotéky",
        "description": "",
        "brandRef": "E5GAVmqco65u7Smx3hso",
        "myBrand": "Česká spořitelna",
        "createdAt": { "_seconds": 1769503575, "_nanoseconds": 556000000 },
        "updatedAt": { "_seconds": 1769503575, "_nanoseconds": 556000000 },
        "createdBy": "hwSqTrrKF1ZaC98LamviUz9Bvqw1",
        "searchTermIds": [],
        "keywords": ""
      }
    ]
  }
}
```

#### Pole response

**`data.topics[]`** – jeden objekt per topic

| Pole | Typ | Popis |
|---|---|---|
| `id` | string | **Unikátní ID topicu** – používej jako `selectedTopic` v reporting endpointech |
| `name` | string | Název topicu, např. `"Brand"`, `"Hypotéky"`, `"Půjčky/Úvěry"` |
| `description` | string | Popis topicu (v praxi vždy prázdný string) |
| `brandRef` | string | ID brandy ke které topic patří |
| `myBrand` | string | Název brandy (s diakritikou), např. `"Česká spořitelna"` |
| `createdAt` | object | Firestore Timestamp – kdy byl topic vytvořen |
| `updatedAt` | object | Firestore Timestamp – kdy byl naposledy upraven; **chybí** u topics bez search termů |
| `createdBy` | string | ID uživatele který topic vytvořil |
| `searchTermIds` | array | Pole ID search termů přiřazených k tomuto topicu; prázdné `[]` pokud žádné nejsou |
| `keywords` | string | Vždy prázdný string – pole se zatím nepoužívá |

> ⚠️ `createdAt` a `updatedAt` jsou Firestore Timestamp – pro převod: `new Date(createdAt._seconds * 1000)`

> ⚠️ `searchTermIds` odkazují na pole `id` z `GET /v1/metrics/search-terms` – jde o ID záznamu prompt×engine, **ne** o ID promptu. Jeden prompt může mít více `searchTermId` (jeden per engine).

> ⚠️ Parametr se jmenuje `brandRef`, ale hodnota je totožná s `brandId` používaným u ostatních endpointů.

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