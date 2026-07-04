# FloodSense-PK Backend (FastAPI + MongoDB)

REST API that serves the complete FloodSense-PK flood-intelligence platform to the **web dashboard** and the **mobile app**:

- Sentinel-1 SAR + U-Net ResNet34 flood detection (Google Earth Engine)
- Live FFD river flows (ffd.pmd.gov.pk) with MongoDB caching
- 2010 Great Flood historical benchmark (Landsat-5 MNDWI)
- Defensible weighted risk scoring + Gemini/Groq strategic insights
- Four-agent disaster workflow (Data Fusion → Intelligence → Simulation → Response)
- RAG Knowledge Assistant (Qdrant + sentence-transformers) with cited sources
- JWT user accounts, per-district alerts, background analysis jobs

---

## Quick start

```bash
# from the project root
pip install -r requirements.txt

# required in .env
#   MONGO_URI=mongodb+srv://...          (required — all data lives in MongoDB)
#   PROJECT_ID=<gcp-project>             (Google Earth Engine project)
#   GEMINI_API_KEY / GROQ_API_KEY        (optional — insights & chat LLM)
#   JWT_SECRET=<random 32+ char string>  (recommended for production)

uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

- Interactive Swagger docs: **http://localhost:8000/docs**
- Health check: **http://localhost:8000/api/health**

### Folder layout

```
backend/
├── app.py            # FastAPI app, CORS, lifespan (Mongo indexes), error handlers
├── config.py         # settings read from .env
├── db.py             # MongoDB client + collections + indexes
├── errors.py         # uniform error envelope + global exception handlers
├── security.py       # bcrypt password hashing + JWT bearer auth
├── schemas.py        # request/response Pydantic models
├── jobs.py           # background job runner (thread pool + Mongo job records)
├── routes/           # all HTTP routes (this file documents every one)
└── services/         # GEE, geodata, rivers, U-Net model, analysis, AI, RAG, pipeline
```

### MongoDB collections

| Collection | Contents |
| ---------- | -------- |
| `users`    | accounts: `username`, `password_hash` (bcrypt), `district` |
| `analyses` | completed district analyses (risk, flood %, map image, river data) |
| `alerts`   | auto / pipeline / manual alerts per district |
| `jobs`     | background analysis job status + results |
| `rivers`   | cached FFD river snapshots |
| `chats`    | RAG chat history |

---

## Conventions

### Success responses

Every successful response includes `"success": true` plus the data documented below.

### Error responses (all endpoints)

Every failure — validation, auth, missing data, downstream outage — uses **one envelope**:

```json
{
  "success": false,
  "error": {
    "code": "DISTRICT_NOT_FOUND",
    "message": "District 'Xyz' was not found. Use GET /api/districts for valid names."
  }
}
```

| HTTP | Common codes |
| ---- | ------------ |
| 400  | `INVALID_SEVERITY`, `NO_DISTRICT_SET` |
| 401  | `UNAUTHORIZED` (missing/expired/invalid token, bad credentials) |
| 404  | `DISTRICT_NOT_FOUND`, `STATION_NOT_FOUND`, `ANALYSIS_NOT_FOUND`, `JOB_NOT_FOUND`, `NO_SAR_IMAGERY`, `IMAGE_NOT_FOUND` |
| 409  | `USERNAME_TAKEN`, `ANALYSIS_ALREADY_RUNNING` |
| 422  | `VALIDATION_ERROR` (includes a `details` list of `{field, message}`) |
| 500  | `INTERNAL_ERROR` |
| 503  | `MONGO_NOT_CONFIGURED`, `MONGO_UNAVAILABLE`, `GEE_UNAVAILABLE`, `MODEL_WEIGHTS_MISSING`, `MODEL_LOAD_FAILED`, `RIVER_DATA_UNAVAILABLE`, `RAG_UNAVAILABLE` |

### Authentication

Protected routes (marked 🔒) require a JWT from register/login:

```
Authorization: Bearer <token>
```

Tokens expire after 7 days (`JWT_EXPIRES_HOURS`).

---

# Route Reference

All routes are prefixed with **`/api`**.

## Health

### `GET /api/health`
Liveness + dependency status. No auth.

**Response 200**
```json
{
  "success": true,
  "status": "ok",
  "mongo": true,
  "gee": {"initialized": false, "error": null},
  "model": {"loaded": false, "error": null},
  "version": "1.0.0"
}
```
`status` is `"degraded"` when Mongo is unreachable. `gee`/`model` initialise lazily on the first analysis, so `false` at boot is normal.

---

## Auth

### `POST /api/auth/register`
Create an account (auto-login: returns a token immediately).

**Request body**
```json
{
  "username": "ali_khan",          // required, 3-64 chars, stored lowercase
  "password": "secret123",         // required, 6-128 chars
  "district": "Larkana"            // optional — home district for alerts
}
```

**Response 201**
```json
{
  "success": true,
  "token": "<jwt>",
  "token_type": "bearer",
  "user": {"id": "665f...", "username": "ali_khan", "district": "Larkana"}
}
```
**Errors:** `409 USERNAME_TAKEN`, `404 DISTRICT_NOT_FOUND`, `422 VALIDATION_ERROR`

### `POST /api/auth/login`

**Request body**
```json
{"username": "ali_khan", "password": "secret123"}
```

**Response 200** — same shape as register.
**Errors:** `401 UNAUTHORIZED`

### `GET /api/auth/me` 🔒
**Response 200**
```json
{"id": "665f...", "username": "ali_khan", "district": "Larkana"}
```

### `PUT /api/auth/me/district` 🔒
Change home district (normalised to the canonical shapefile name).

**Request body**
```json
{"district": "Sukkur"}
```
**Response 200** — updated user object (same shape as `/me`).
**Errors:** `404 DISTRICT_NOT_FOUND`

---

## Districts

### `GET /api/districts`
All district names for pickers/dropdowns.

**Query params:** `priority_only` (bool, default `false`) — only flood-priority districts.

**Response 200**
```json
{
  "success": true,
  "count": 145,
  "districts": [
    {"name": "Larkana", "is_priority": true},
    {"name": "Lahore", "is_priority": false}
  ]
}
```

### `GET /api/districts/{name}`
Metadata for one district (exact then partial, case-insensitive match).

**Response 200**
```json
{
  "success": true,
  "district": {
    "name": "Larkana",
    "bbox": [67.95, 27.13, 68.50, 27.93],
    "centroid": {"lat": 27.517, "lon": 68.194},
    "area_km2": 1831.8,
    "is_priority": true
  }
}
```

### `GET /api/districts/{name}/geometry`
District boundary as GeoJSON (for map layers).

**Response 200**
```json
{
  "success": true,
  "feature": {
    "type": "Feature",
    "properties": {"district": "Larkana", "bbox": [67.95, 27.13, 68.5, 27.93]},
    "geometry": {"type": "MultiPolygon", "coordinates": [...]}
  }
}
```

---

## Rivers (live FFD data)

### `GET /api/rivers`
All FFD gauge/barrage stations. Served from the Mongo cache when fresh, scraped live otherwise.

**Query params:** `max_age_minutes` (int 0-1440, default 30), `force_refresh` (bool, default `false`).

**Response 200**
```json
{
  "success": true,
  "count": 31,
  "stations": [
    {
      "station": "Guddu Barrage",
      "river": "Indus",
      "inflow": 74000,
      "outflow": 68000,
      "status": "NORMAL",           // NORMAL | HIGH | EXTREME | UNKNOWN
      "inflow_trend": "Rising",
      "outflow_trend": "Steady",
      "recorded": "02-07-2026 06:00"
    }
  ],
  "fetched_at": "2026-07-02T14:00:00+00:00",
  "source": "live"                  // live | cache | stale-cache
}
```
**Errors:** `503 RIVER_DATA_UNAVAILABLE` (live fetch failed and no cache exists yet)

### `GET /api/rivers/{station_name}`
One station by partial, case-insensitive name (e.g. `guddu`).

**Response 200:** `{"success": true, "station": {…as above…}, "fetched_at": "...", "source": "cache"}`
**Errors:** `404 STATION_NOT_FOUND`

---

## Analysis (SAR + U-Net + risk)

Running an analysis takes **30s–3min** (GEE download + tiled U-Net inference), so it runs as a background job.

**Client flow:**
1. `POST /api/analysis/{district}` → get `job_id`
2. Poll `GET /api/jobs/{job_id}` every few seconds until `status` is `complete` (or `failed`)
3. Read `GET /api/analysis/{district}/latest` (and `/image` for the flood map)

### `POST /api/analysis/{district}`
Queue a full analysis. No body.

**Response 202**
```json
{
  "success": true,
  "job_id": "3f2a9c...",
  "status": "queued",
  "district": "Larkana",
  "message": "Analysis queued. Poll GET /api/jobs/3f2a9c... for progress."
}
```
**Errors:** `404 DISTRICT_NOT_FOUND`, `409 ANALYSIS_ALREADY_RUNNING` (one active job per district)

### `GET /api/jobs/{job_id}`
**Response 200**
```json
{
  "success": true,
  "job": {
    "id": "665f...",
    "job_id": "3f2a9c...",
    "type": "district_analysis",
    "district": "Larkana",
    "status": "running",            // queued | running | complete | failed
    "result": null,                 // analysis summary once complete
    "error": null,                  // failure message when failed
    "created_at": "2026-07-02T14:00:00+00:00",
    "updated_at": "2026-07-02T14:00:05+00:00"
  }
}
```
Jobs stuck `running` > 30 min (e.g. server restart) are reported as `failed`.
**Errors:** `404 JOB_NOT_FOUND`

### `GET /api/analysis`
Newest analysis per district, sorted by risk — the national overview screen.

**Query params:** `limit` (1-500, default 200).

**Response 200:** `{"success": true, "count": 4, "analyses": [ {…analysis doc, no image…} ]}`

### `GET /api/analysis/{district}/latest`
The most recent stored analysis.

**Query params:** `include_image` (bool, default `false`) — include the base64 PNG (large; prefer the `/image` endpoint).

**Response 200**
```json
{
  "success": true,
  "analysis": {
    "id": "665f...",
    "district": "Larkana",
    "risk_score": 4.6,                    // 1-10 weighted defensible score
    "risk_level": "MODERATE RISK",        // LOW RISK | MODERATE RISK | HIGH RISK
    "flood_pct_current": 3.42,            // % of district under water now (U-Net)
    "flood_pct_2010": 6.91,               // 2010 benchmark %
    "delta_vs_2010": -3.49,
    "affected_area_km2": 62.7,
    "flood_pixels": 8963,
    "settlement_risk": "low",             // low | medium | high
    "confidence": "high",
    "model_used": "U-Net ResNet34 (Tiled Inference Mode)",
    "sar_window": {"start": "2026-06-02", "end": "2026-07-02", "size_px": 512},
    "bbox": [67.95, 27.13, 68.50, 27.93],
    "river": {"station": "...", "inflow": 74000, "outflow": 68000, "status": "NORMAL", "...": "..."},
    "created_at": "2026-07-02T14:03:11+00:00"
  }
}
```
**Errors:** `404 ANALYSIS_NOT_FOUND` (no analysis run yet)

### `GET /api/analysis/{district}/image`
Latest flood-map overlay (SAR backdrop + blue U-Net mask) as a **raw PNG** — point an `<img src>` / `Image.network()` straight at it.

**Response 200:** binary `image/png`.
**Errors:** `404 ANALYSIS_NOT_FOUND`, `404 IMAGE_NOT_FOUND`

### `GET /api/analysis/{district}/insights`
Gemini/Groq strategic report grounded in the latest analysis (falls back to a simulated report when no LLM key is set — never hard-fails).

**Response 200**
```json
{
  "success": true,
  "district": "Larkana",
  "insights": "1. [SITUATION SUMMARY] ...",
  "llm_used": true,
  "based_on_analysis_id": "665f..."
}
```
**Errors:** `404 ANALYSIS_NOT_FOUND`

---

## Agent Pipeline (Agentic Command Center)

### `POST /api/pipeline/{district}`
Run the four-agent workflow (Data Fusion → Disaster Intelligence → Simulation → Response) on the latest analysis. The citizen + authority alerts it produces are persisted to the alerts collection.

**Request body (optional)**
```json
{"population_at_risk": 25000}    // omit to estimate from affected km² × 350
```

**Response 200**
```json
{
  "success": true,
  "pipeline": {
    "district": "Larkana",
    "assessment": {
      "risk_level": "MODERATE RISK",
      "flood_coverage_percentage": 3.42,
      "explanation": "...",
      "recommended_action": "..."
    },
    "progression": {
      "horizons": [
        {"hours": 6, "projected_coverage_percentage": 4.1, "...": "..."}
      ],
      "...": "..."
    },
    "recommended_safe_zone": null,
    "evacuation_route": null,
    "citizen_alert": "FLOOD ALERT for Larkana ...",
    "authority_alert": "SITUATION REPORT ...",
    "population_at_risk": 21945,
    "rag_sources": ["NDMA Flood Protocol ..."],
    "based_on_analysis_id": "665f..."
  }
}
```
**Errors:** `404 ANALYSIS_NOT_FOUND` (run `POST /api/analysis/{district}` first), `404 DISTRICT_NOT_FOUND`

---

## Alerts

### `GET /api/alerts`
Newest alerts first. No auth (public safety data).

**Query params:** `district` (name filter), `severity` (`LOW|MODERATE|HIGH`), `limit` (1-200, default 50).

**Response 200**
```json
{
  "success": true,
  "count": 2,
  "alerts": [
    {
      "id": "665f...",
      "district": "Larkana",
      "severity": "HIGH",              // LOW | MODERATE | HIGH
      "risk_score": 7.2,               // present on auto-analysis alerts
      "message": "HIGH flood risk in Larkana: ...",
      "audience": "citizen",           // citizen | authority (pipeline alerts only)
      "source": "auto-analysis",       // auto-analysis | pipeline | manual
      "issued_by": "admin",            // manual alerts only
      "created_at": "2026-07-02T14:05:00+00:00"
    }
  ]
}
```
**Errors:** `400 INVALID_SEVERITY`, `404 DISTRICT_NOT_FOUND`

### `GET /api/alerts/mine` 🔒
Alerts for the authenticated user's home district (mobile home screen).

**Response 200:** `{"success": true, "district": "Larkana", "count": 1, "alerts": [...]}`
**Errors:** `400 NO_DISTRICT_SET`

### `POST /api/alerts` 🔒
Manually issue an alert (e.g. an authority operator).

**Request body**
```json
{
  "district": "Sukkur",
  "severity": "HIGH",                   // LOW | MODERATE | HIGH
  "message": "Evacuate low-lying areas near the barrage."
}
```
**Response 201:** `{"success": true, "alert": {…stored alert…}}`
**Errors:** `401 UNAUTHORIZED`, `404 DISTRICT_NOT_FOUND`, `422 VALIDATION_ERROR`

Alerts are also created automatically:
- **auto-analysis** — whenever a completed analysis scores ≥ 4/10 (`MODERATE`) or ≥ 7/10 (`HIGH`);
- **pipeline** — every `POST /api/pipeline/{district}` stores its citizen + authority alerts.

---

## Knowledge Chat (RAG)

### `POST /api/chat`
Grounded Q&A over the flood knowledge base (NDMA protocols, river systems, architecture PDF). Answers cite sources. The **first call is slow (~30s)** while the embedding model loads and ingestion runs; later calls are fast.

**Request body**
```json
{
  "question": "What should Nowshera residents do when the Kabul River is HIGH?",
  "top_k": 3                            // optional, 1-10, default 3
}
```

**Response 200**
```json
{
  "success": true,
  "question": "...",
  "answer": "According to NDMA protocol ...",
  "sources": [
    {"source": "FloodSense-PK Architecture.pdf", "section": "Alert Protocols", "page_number": 12}
  ],
  "llm_used": true                      // false → answer contains raw retrieved context
}
```
**Errors:** `503 RAG_UNAVAILABLE`, `422 VALIDATION_ERROR`

### `GET /api/chat/history`
Recent Q&A history, newest first. **Query params:** `limit` (1-200, default 50).

**Response 200:** `{"success": true, "count": 12, "messages": [{question, answer, sources, llm_used, created_at}]}`

---

## Typical client flows

**Mobile home screen** (after login):
`GET /api/auth/me` → `GET /api/analysis/{user.district}/latest` → `GET /api/analysis/{user.district}/image` → `GET /api/alerts/mine`

**Web national dashboard:**
`GET /api/analysis` (risk-ranked table) → `GET /api/rivers` (hydraulic panel) → `GET /api/districts/{name}/geometry` (map shapes)

**Refreshing a district:**
`POST /api/analysis/{district}` → poll `GET /api/jobs/{job_id}` → `GET /api/analysis/{district}/latest` → optionally `POST /api/pipeline/{district}` for the agentic report.
