# India Ambulance Dispatch MVP - Recommended Stack (Actionable)

## 1) MVP Scope (what we are building now)

- Patient app: SOS in 2 taps, live ETA, ambulance type, fare estimate
- Ambulance app: accept/decline, navigation handoff, status milestones
- Dispatch console: auto-assign nearest fit ambulance, manual override, SLA dashboard
- Hospital console: incoming case alert, bed capability flags, handover timestamps

This MVP excludes full call-center replacement. It uses digital triage + escalation rules.

## 2) Recommended MVP Stack (selected)

### Frontend
- Patient app: Flutter (Android-first release)
- Ambulance app: Flutter (shared codebase with patient app)
- Dispatch + Hospital console: React + Vite + TypeScript

### Backend
- API: Node.js + TypeScript + NestJS
- Realtime: WebSocket (Socket.IO)
- Queue/jobs: Redis + BullMQ

### Data and Geo
- Primary DB: PostgreSQL + PostGIS
- Fast candidate search: H3 cell indexing + PostGIS fallback
- Cache + presence: Redis

### Routing and ETA
- Primary maps: Google Maps Platform or Mapbox Directions/Matrix
- ETA strategy: H3 shortlist first, then route ETA for top candidates

### Cloud/DevOps
- Cloud: AWS (or GCP equivalent)
- Container: Docker
- Orchestration (phase 2): Kubernetes
- Observability: Prometheus + Grafana + Sentry

## 3) Core Dispatch Method (Uber-like but medical-safe)

### Step A: Patient location intake
- Capture: lat, lon, gpsAccuracyMeters, timestamp
- Reject stale locations (> 15 sec) and request refresh
- Snap to road where possible

### Step B: Candidate ambulance discovery
- Query ambulances by status = AVAILABLE and recent heartbeat (< 10 sec)
- Find nearby H3 cells (ring expansion): k=1,2,3...
- Filter by clinical fit:
  - RED severity: ALS preferred, BLS fallback allowed by policy
  - AMBER/GREEN: BLS acceptable

### Step C: Score and assign
Use score (lower is better):

score = 0.55*etaMinutes + 0.20*clinicalPenalty + 0.15*reliabilityPenalty + 0.10*hospitalPenalty

Where:
- etaMinutes: live route ETA to pickup
- clinicalPenalty: mismatch penalty (0 if fit, high if not)
- reliabilityPenalty: cancellation history, late arrival rate, app uptime
- hospitalPenalty: destination not ready / capacity constraints

Assignment policy:
- RED: multicast top 3 simultaneously, first accept wins
- AMBER/GREEN: sequential ping top N with 8-12 second timeout

## 4) Digital Triage (no heavy calling)

Input in <= 15 seconds:
- Incident type: trauma/chest pain/breathing/unconscious/pregnancy/other
- Conscious? (yes/no)
- Breathing normally? (yes/no)
- Severe bleeding? (yes/no)

Rules:
- RED if unconscious OR not breathing OR severe bleeding
- AMBER if high-risk symptom but stable vitals by responses
- GREEN for non-critical transport

Escalate to live call only when:
- location uncertain
- no ambulance accepted in SLA window
- RED case + triage ambiguity

## 5) Minimal Data Model

### ambulances
- id (uuid)
- vehicle_type (BLS/ALS/ICU)
- current_lat, current_lon
- h3_cell
- status (AVAILABLE/ENROUTE/AT_SCENE/TRANSPORTING/OFFLINE)
- last_heartbeat_at
- reliability_score

### incidents
- id (uuid)
- patient_id
- severity (RED/AMBER/GREEN)
- incident_type
- pickup_lat, pickup_lon
- pickup_h3_cell
- created_at
- status (CREATED/DISPATCHING/ASSIGNED/PICKED_UP/HANDED_OVER/CLOSED)

### dispatch_attempts
- id
- incident_id
- ambulance_id
- eta_minutes
- score
- pinged_at
- accepted_at
- declined_at
- timeout_at

### hospitals
- id
- name
- lat, lon
- trauma_ready (bool)
- icu_available (bool)
- emergency_accepting (bool)
- handover_avg_minutes

## 6) API Surface (MVP)

### Patient
- POST /incidents/sos
- GET /incidents/:id/status
- GET /incidents/:id/track

### Ambulance
- POST /ambulances/:id/heartbeat
- POST /dispatch/:attemptId/accept
- POST /dispatch/:attemptId/decline
- POST /incidents/:id/milestone  (ENROUTE, AT_SCENE, PICKED_UP, HANDED_OVER)

### Dispatch Console
- POST /dispatch/run/:incidentId
- POST /dispatch/manual-assign
- GET /sla/live

### Hospital Console
- POST /hospitals/:id/capacity
- POST /incidents/:id/handover

## 7) SLA Targets for Pilot City

- Dispatch decision: <= 15 seconds
- Ambulance acceptance (RED): <= 30 seconds
- Pickup ETA prediction error: <= 20%
- App heartbeat loss alert: <= 20 seconds

## 8) 2-Week Build Plan

### Week 1
- Setup backend skeleton (NestJS + Postgres + Redis)
- Implement ambulance heartbeat + availability state machine
- Implement SOS API + digital triage rules
- Implement H3-based shortlist + PostGIS fallback query
- Integrate directions ETA for top candidates

### Week 2
- Implement dispatch policies (RED multicast, AMBER/GREEN sequential)
- Build minimal patient/ambulance app screens
- Build dispatch web console with live map and manual override
- Add SLA metrics and basic alerting
- Pilot dry runs with mocked city traffic + synthetic incidents

## 9) Build Order (strict)

1. Ambulance telemetry + heartbeat reliability
2. Incident creation + triage
3. Candidate search + ranking
4. Dispatch loop + retries/fallback
5. Realtime tracking + milestone updates
6. Hospital handover and closure events

## 10) Risks and Mitigations

- GPS drift / weak signal: use accuracy radius + stale location rejection
- Driver app offline: heartbeat watchdog and auto OFFLINE
- No acceptance in hotspot areas: radius expansion + partner fleet routing
- Hospital refusal: destination recommendation with acceptance flags

## 11) Go-Live Pilot Recommendation (India)

- Start in 1 metro zone + 20-50 ambulances + 5-10 hospitals
- Run 2 modes initially:
  - emergency RED/AMBER
  - urgent inter-facility transfers
- Add 24x7 dispatcher supervision for exception handling

---

If needed, next step is to generate:
- SQL migrations for this schema
- NestJS service skeleton for dispatch scoring
- Flutter screen flow for patient/ambulance apps
