from __future__ import annotations

import random
import string
import time
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .dispatch import haversine_km, rank_candidates, to_geohash, to_h3_cell
from .hospital_routing import (
    estimate_transport_cost,
    evaluate_hospital_safety,
    recommend_hospitals,
    required_capabilities,
)
from .models import (
    Ambulance,
    DispatchAction,
    DispatchRespondInput,
    HeartbeatInput,
    Hospital,
    HospitalSelectInput,
    Incident,
    IncidentType,
    Severity,
    SosInput,
)
from .store import store

app = FastAPI(title="Ambulance MVP Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def derive_severity(payload: SosInput) -> Severity:
    if not payload.conscious or not payload.breathingNormally or payload.severeBleeding:
        return Severity.RED

    if payload.incidentType in (
        IncidentType.CHEST_PAIN,
        IncidentType.BREATHING,
        IncidentType.PREGNANCY,
    ):
        return Severity.AMBER

    return Severity.GREEN


def new_incident_id() -> str:
    token = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    return f"inc_{token}"


def _seed_hospitals() -> None:
    if store.hospitals:
        return

    seed_data = [
        Hospital(
            id="HSP-001",
            name="CityCare Trauma & ER",
            lat=12.9722,
            lon=77.5933,
            emergencyAccepting=True,
            capabilities=["ER", "TRAUMA", "ICU", "RESPIRATORY"],
            handoverAvgMinutes=14,
            capacityLoad=0.45,
            insuranceNetworks=["STAR", "HDFC", "ICICI"],
        ),
        Hospital(
            id="HSP-002",
            name="Metro Heart Institute",
            lat=12.981,
            lon=77.606,
            emergencyAccepting=True,
            capabilities=["ER", "CARDIAC", "ICU", "CRITICAL_CARE"],
            handoverAvgMinutes=18,
            capacityLoad=0.35,
            insuranceNetworks=["NIVA", "STAR", "CARE"],
        ),
        Hospital(
            id="HSP-003",
            name="Mother & Child Emergency Center",
            lat=12.965,
            lon=77.584,
            emergencyAccepting=True,
            capabilities=["ER", "OBGYN", "ICU", "CRITICAL_CARE"],
            handoverAvgMinutes=12,
            capacityLoad=0.4,
            insuranceNetworks=["HDFC", "BAJAJ", "NIVA"],
        ),
        Hospital(
            id="HSP-004",
            name="General Multispeciality Hospital",
            lat=12.955,
            lon=77.61,
            emergencyAccepting=True,
            capabilities=["ER", "TRAUMA", "CARDIAC", "RESPIRATORY", "ICU", "CRITICAL_CARE"],
            handoverAvgMinutes=20,
            capacityLoad=0.65,
            insuranceNetworks=["STAR", "NIVA", "HDFC", "ICICI", "CARE"],
        ),
    ]

    for hospital in seed_data:
        store.hospitals[hospital.id] = hospital


_seed_hospitals()


def _new_dispatch_state(incident: Incident, candidates: list[dict]) -> dict:
    mode = "MULTICAST" if incident.severity == Severity.RED else "SEQUENTIAL"
    ordered_ids = [c["ambulanceId"] for c in candidates]
    state = {
        "incidentId": incident.id,
        "mode": mode,
        "status": "DISPATCHING",
        "offers": {},
        "queue": [],
        "orderedCandidates": ordered_ids,
        "assignedAmbulanceId": None,
        "lastUpdatedAt": int(time.time() * 1000),
    }

    now_ms = int(time.time() * 1000)
    if mode == "MULTICAST":
        for amb_id in ordered_ids[:3]:
            state["offers"][amb_id] = {
                "status": "PENDING",
                "pingedAt": now_ms,
                "respondedAt": None,
            }
        state["queue"] = ordered_ids[3:]
    else:
        if ordered_ids:
            first_id = ordered_ids[0]
            state["offers"][first_id] = {
                "status": "PENDING",
                "pingedAt": now_ms,
                "respondedAt": None,
            }
            state["queue"] = ordered_ids[1:]

    return state


def _maybe_progress_dispatch(incident: Incident) -> dict | None:
    dispatch = store.dispatches.get(incident.id)
    if not dispatch:
        return None

    if dispatch["status"] in ("ASSIGNED", "EXHAUSTED"):
        return dispatch

    now_ms = int(time.time() * 1000)
    timeout_ms = 12000

    for offer in dispatch["offers"].values():
        if offer["status"] == "PENDING" and now_ms - offer["pingedAt"] > timeout_ms:
            offer["status"] = "TIMEOUT"
            offer["respondedAt"] = now_ms

    pending_exists = any(offer["status"] == "PENDING" for offer in dispatch["offers"].values())
    if not pending_exists and dispatch["mode"] == "SEQUENTIAL" and dispatch["queue"]:
        next_id = dispatch["queue"].pop(0)
        dispatch["offers"][next_id] = {
            "status": "PENDING",
            "pingedAt": now_ms,
            "respondedAt": None,
        }

    pending_exists = any(offer["status"] == "PENDING" for offer in dispatch["offers"].values())
    if not pending_exists and not dispatch["queue"] and dispatch["assignedAmbulanceId"] is None:
        dispatch["status"] = "EXHAUSTED"
        incident.status = "DISPATCH_FAILED"
        store.incidents[incident.id] = incident

    dispatch["lastUpdatedAt"] = now_ms
    store.dispatches[incident.id] = dispatch
    return dispatch


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ambulances/{ambulance_id}/heartbeat")
def ambulance_heartbeat(ambulance_id: str, payload: HeartbeatInput) -> dict[str, bool]:
    store.ambulances[ambulance_id] = Ambulance(
        id=ambulance_id,
        type=payload.type,
        status=payload.status,
        lat=payload.lat,
        lon=payload.lon,
        h3Cell=to_h3_cell(payload.lat, payload.lon),
        geohash=to_geohash(payload.lat, payload.lon),
        lastHeartbeatAt=int(time.time() * 1000),
        reliabilityScore=payload.reliabilityScore,
    )
    return {"success": True}


@app.post("/api/incidents/sos")
def incident_sos(payload: SosInput) -> dict:
    incident = Incident(
        id=new_incident_id(),
        incidentType=payload.incidentType,
        severity=derive_severity(payload),
        pickupLat=payload.pickupLat,
        pickupLon=payload.pickupLon,
        pickupH3Cell=to_h3_cell(payload.pickupLat, payload.pickupLon),
        pickupGeohash=to_geohash(payload.pickupLat, payload.pickupLon),
        createdAt=int(time.time() * 1000),
        status="DISPATCHING",
    )
    store.incidents[incident.id] = incident

    candidates = rank_candidates(incident, store.ambulances.values())
    dispatch_state = _new_dispatch_state(incident, [c.model_dump() for c in candidates])
    store.dispatches[incident.id] = dispatch_state
    dispatch_state = _maybe_progress_dispatch(incident)
    store.incidents[incident.id] = incident

    return {
        "incident": incident.model_dump(),
        "dispatch": {
            "assigned": None,
            "topCandidates": [c.model_dump() for c in candidates[:3]],
            "state": dispatch_state,
        },
    }


@app.get("/api/incidents/{incident_id}/status")
def incident_status(incident_id: str) -> dict:
    incident = store.incidents.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    dispatch_state = _maybe_progress_dispatch(incident)
    return {"incident": incident.model_dump(), "dispatch": dispatch_state}


@app.get("/api/hospitals")
def list_hospitals() -> dict:
    return {"hospitals": [h.model_dump() for h in store.hospitals.values()]}


@app.get("/api/incidents/{incident_id}/hospitals/recommendations")
def hospital_recommendations(incident_id: str, insurance: Optional[str] = None) -> dict:
    incident = store.incidents.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    recommendations = recommend_hospitals(
        incident=incident,
        hospitals=list(store.hospitals.values()),
        insurance=insurance,
        top_n=3,
    )

    required = required_capabilities(incident.incidentType, incident.severity)

    return {
        "incidentId": incident_id,
        "selectedHospitalId": incident.selectedHospitalId,
        "requiredCapabilities": required,
        "recommendations": [item.model_dump() for item in recommendations],
    }


@app.post("/api/incidents/{incident_id}/hospital/select")
def select_hospital(incident_id: str, payload: HospitalSelectInput) -> dict:
    incident = store.incidents.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    hospital = store.hospitals.get(payload.hospitalId)
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    recommendations = recommend_hospitals(
        incident=incident,
        hospitals=list(store.hospitals.values()),
        insurance=None,
        top_n=3,
    )
    top_recommendation_id = recommendations[0].hospitalId if recommendations else None
    is_override = bool(top_recommendation_id and hospital.id != top_recommendation_id)

    distance_km = haversine_km(incident.pickupLat, incident.pickupLon, hospital.lat, hospital.lon)
    cost_quote = estimate_transport_cost(incident, distance_km, is_override=is_override)

    incident.selectedHospitalId = hospital.id
    incident.selectedHospitalReason = payload.reason
    store.incidents[incident_id] = incident

    safety = evaluate_hospital_safety(incident, hospital)
    warning = None
    if safety["isUnsafeForRed"]:
        warning = {
            "code": "UNSAFE_RED_OVERRIDE",
            "message": "Selected hospital does not meet required RED-case capabilities.",
            "missingCapabilities": safety["missingCapabilities"],
        }

    return {
        "incident": incident.model_dump(),
        "selectedHospital": hospital.model_dump(),
        "overrideApplied": is_override,
        "recommendedHospitalId": top_recommendation_id,
        "costQuote": cost_quote,
        "safety": safety,
        "warning": warning,
    }


@app.get("/api/dispatch/candidates/{incident_id}")
def dispatch_candidates(incident_id: str) -> dict:
    incident = store.incidents.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    candidates = rank_candidates(incident, store.ambulances.values())
    return {"candidates": [c.model_dump() for c in candidates[:10]]}


@app.get("/api/dispatch/state/{incident_id}")
def dispatch_state(incident_id: str) -> dict:
    incident = store.incidents.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    dispatch = _maybe_progress_dispatch(incident)
    if not dispatch:
        raise HTTPException(status_code=404, detail="Dispatch not found")

    return {"dispatch": dispatch, "incident": incident.model_dump()}


@app.post("/api/dispatch/{incident_id}/respond")
def dispatch_respond(incident_id: str, payload: DispatchRespondInput) -> dict:
    incident = store.incidents.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    dispatch = _maybe_progress_dispatch(incident)
    if not dispatch:
        raise HTTPException(status_code=404, detail="Dispatch not found")

    offer = dispatch["offers"].get(payload.ambulanceId)
    if not offer:
        raise HTTPException(status_code=400, detail="Ambulance has no active offer for this incident")

    if offer["status"] != "PENDING":
        raise HTTPException(status_code=400, detail=f"Offer is not pending. Current state: {offer['status']}")

    now_ms = int(time.time() * 1000)
    if payload.action == DispatchAction.DECLINE:
        offer["status"] = "DECLINED"
        offer["respondedAt"] = now_ms
    else:
        offer["status"] = "ACCEPTED"
        offer["respondedAt"] = now_ms
        dispatch["status"] = "ASSIGNED"
        dispatch["assignedAmbulanceId"] = payload.ambulanceId
        incident.status = "ASSIGNED"
        incident.assignedAmbulanceId = payload.ambulanceId

        amb = store.ambulances.get(payload.ambulanceId)
        if amb:
            amb.status = "ENROUTE"
            store.ambulances[payload.ambulanceId] = amb

        for amb_id, other_offer in dispatch["offers"].items():
            if amb_id != payload.ambulanceId and other_offer["status"] == "PENDING":
                other_offer["status"] = "CANCELLED"
                other_offer["respondedAt"] = now_ms

    store.incidents[incident.id] = incident
    store.dispatches[incident.id] = dispatch
    dispatch = _maybe_progress_dispatch(incident)
    return {"incident": incident.model_dump(), "dispatch": dispatch}


@app.get("/api/debug/state")
def debug_state() -> dict:
    return {
        "ambulances": [a.model_dump() for a in store.ambulances.values()],
        "incidents": [i.model_dump() for i in store.incidents.values()],
        "dispatches": list(store.dispatches.values()),
        "hospitals": [h.model_dump() for h in store.hospitals.values()],
    }
