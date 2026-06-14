# Ambulance Service MVP (Python Backend + React Frontend)

This workspace now contains a runnable MVP implementation:

- `backend-python`: FastAPI backend for SOS, heartbeat, dispatch orchestration, hospital recommendations, and pricing
- `frontend`: React web console to simulate patient SOS, ambulance responses, hospital recommendation, and override selection

## 1) Run Python Backend

```bash
cd backend-python
pip install -r requirements.txt
uvicorn app.main:app --reload --port 4000
```

Backend URL: `http://localhost:4000`

## 2) Run Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://localhost:5173`

## 3) MVP Test Flow

1. Open frontend UI.
2. In "Ambulance Heartbeat", send 1-2 ambulances as `AVAILABLE` with nearby coordinates.
3. In "Patient SOS", trigger incident with pickup location.
4. Observe assigned ambulance and top candidates in output panel.

## API Endpoints

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

## Live ETA Provider Setup (Optional)

Dispatch can use live road ETA from Mapbox or Google. If no provider is configured, it falls back to approximate ETA.

Mapbox:

```bash
set MAPS_PROVIDER=mapbox
set MAPBOX_TOKEN=your_mapbox_token
```

Google:

```bash
set MAPS_PROVIDER=google
set GOOGLE_MAPS_API_KEY=your_google_key
```

Candidate responses include `etaSource` as `mapbox`, `google`, or `approx`.

## Notes

- Dispatch uses H3/geohash shortlist + haversine scoring + severity fit + reliability.
- RED incidents use multicast (top 3). AMBER/GREEN use sequential retries.
- Hospital flow supports Top 3 recommendations and manual override for insurance/doctor/financial preference.
- RED recommendations are hard-filtered by required capability; unsafe RED override returns a warning payload.
- User override is always accepted and persisted.
- Hospital selection response includes a cost quote breakdown:
	- `baseFare`
	- `distanceCharge`
	- `severitySurcharge`
	- `overrideSurcharge`
	- `total`
- If selected hospital differs from top recommendation, `overrideApplied=true` and extra `overrideSurcharge` is added.
- Data store is in-memory for MVP; restart clears all data.
- Current frontend targets backend at `http://localhost:4000`.
