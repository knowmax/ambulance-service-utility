# Ambulance Backend (Python)

FastAPI implementation of the MVP dispatch engine.

## Run

1. Create and activate a Python environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start server:

```bash
uvicorn app.main:app --reload --port 4000
```

Server runs on `http://localhost:4000` to stay compatible with the frontend.

## Endpoints

- `GET /health`
- `POST /api/ambulances/{id}/heartbeat`
- `POST /api/incidents/sos`
- `GET /api/incidents/{id}/status`
- `GET /api/dispatch/candidates/{incident_id}`
- `GET /api/dispatch/state/{incident_id}`
- `POST /api/dispatch/{incident_id}/respond`
- `GET /api/hospitals`
- `GET /api/incidents/{incident_id}/hospitals/recommendations?insurance=STAR`
- `POST /api/incidents/{incident_id}/hospital/select`
- `GET /api/debug/state`

## What changed

- Candidate shortlist now uses real `H3` ring expansion with `geohash` fallback.
- Dispatch strategy:
	- `RED`: multicast offers to top 3 ambulances in parallel.
	- `AMBER/GREEN`: sequential offer, one-by-one with timeout retry.
- Ambulance acceptance/decline is handled with `POST /api/dispatch/{incident_id}/respond`.

## Live Route ETA Integration

Dispatch ranking can use live road ETA from Mapbox or Google.

Set environment variables before running:

- `MAPS_PROVIDER=mapbox` with `MAPBOX_TOKEN=...`
- or `MAPS_PROVIDER=google` with `GOOGLE_MAPS_API_KEY=...`

If provider is not configured or API call fails, backend automatically falls back to approximate ETA.

Candidate output includes `etaSource` as `mapbox`, `google`, or `approx`.

## Hospital Recommendation + Override

- System returns Top 3 hospitals for an incident based on ETA, handover delay, capacity, capability fit, and insurance hint.
- For `RED` incidents, recommendations are hard-filtered to only clinically capable hospitals.
- Users can override and choose any hospital via `POST /api/incidents/{incident_id}/hospital/select`.
- Incident stores `selectedHospitalId` and `selectedHospitalReason` for auditability.
- If a `RED` override is unsafe, response includes warning `UNSAFE_RED_OVERRIDE` and missing capabilities.
- Hospital selection response includes `costQuote` with base fare, distance charge, severity surcharge, and override surcharge.
- If selected hospital differs from top recommended hospital, `overrideApplied=true` and extra `overrideSurcharge` is added.
