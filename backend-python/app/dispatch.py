from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterable

import h3
import pygeohash as pgh

from .models import Ambulance, DispatchCandidate, Incident

AVG_CITY_SPEED_KMPH = 24.0
H3_RESOLUTION = 9
MAX_LIVE_ETA_CANDIDATES = 10
REQUEST_TIMEOUT_SECONDS = 2.5


def _to_radians(value: float) -> float:
    return value * math.pi / 180.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0
    dlat = _to_radians(lat2 - lat1)
    dlon = _to_radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(_to_radians(lat1))
        * math.cos(_to_radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2 * earth_radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def clinical_penalty(incident: Incident, ambulance: Ambulance) -> float:
    if incident.severity == "RED":
        if ambulance.type in ("ALS", "ICU"):
            return 0.0
        return 30.0
    return 0.0


def _build_fallback_eta_minutes(distance_km: float) -> float:
    return max(1.0, (distance_km / AVG_CITY_SPEED_KMPH) * 60.0)


def _provider_name() -> str:
    return os.getenv("MAPS_PROVIDER", "none").strip().lower()


def _fetch_mapbox_eta_minutes(
    origin_lat: float,
    origin_lon: float,
    destinations: list[tuple[str, float, float]],
) -> dict[str, float]:
    token = os.getenv("MAPBOX_TOKEN", "").strip()
    if not token or not destinations:
        return {}

    coord_items = [f"{origin_lon},{origin_lat}"]
    coord_items.extend([f"{lon},{lat}" for _amb_id, lat, lon in destinations])
    coords = ";".join(coord_items)
    query = urllib.parse.urlencode({"sources": "0", "annotations": "duration", "access_token": token})
    url = f"https://api.mapbox.com/directions-matrix/v1/mapbox/driving/{coords}?{query}"

    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {}

    durations = payload.get("durations")
    if not isinstance(durations, list) or not durations:
        return {}

    first_row = durations[0]
    if not isinstance(first_row, list):
        return {}

    out: dict[str, float] = {}
    for idx, (amb_id, _lat, _lon) in enumerate(destinations, start=1):
        if idx >= len(first_row):
            continue
        value = first_row[idx]
        if isinstance(value, (int, float)) and value > 0:
            out[amb_id] = round(float(value) / 60.0, 2)

    return out


def _fetch_google_eta_minutes(
    origin_lat: float,
    origin_lon: float,
    destinations: list[tuple[str, float, float]],
) -> dict[str, float]:
    key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not key or not destinations:
        return {}

    dest_str = "|".join([f"{lat},{lon}" for _amb_id, lat, lon in destinations])
    query = urllib.parse.urlencode(
        {
            "origins": f"{origin_lat},{origin_lon}",
            "destinations": dest_str,
            "mode": "driving",
            "departure_time": "now",
            "key": key,
        }
    )
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json?{query}"

    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {}

    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        return {}
    first_row = rows[0]
    if not isinstance(first_row, dict):
        return {}

    elements = first_row.get("elements")
    if not isinstance(elements, list):
        return {}

    out: dict[str, float] = {}
    for idx, (amb_id, _lat, _lon) in enumerate(destinations):
        if idx >= len(elements):
            continue
        element = elements[idx]
        if not isinstance(element, dict):
            continue
        if element.get("status") != "OK":
            continue

        duration_obj = element.get("duration_in_traffic") or element.get("duration")
        if not isinstance(duration_obj, dict):
            continue
        seconds = duration_obj.get("value")
        if isinstance(seconds, (int, float)) and seconds > 0:
            out[amb_id] = round(float(seconds) / 60.0, 2)

    return out


def _fetch_live_eta_minutes(
    incident: Incident,
    ambulances: list[Ambulance],
) -> tuple[dict[str, float], str]:
    provider = _provider_name()
    if provider not in ("mapbox", "google"):
        return {}, "approx"

    subset = ambulances[:MAX_LIVE_ETA_CANDIDATES]
    destinations = [(amb.id, amb.lat, amb.lon) for amb in subset]

    if provider == "mapbox":
        etas = _fetch_mapbox_eta_minutes(incident.pickupLat, incident.pickupLon, destinations)
    else:
        etas = _fetch_google_eta_minutes(incident.pickupLat, incident.pickupLon, destinations)

    if not etas:
        return {}, "approx"
    return etas, provider


def to_h3_cell(lat: float, lon: float) -> str:
    return h3.latlng_to_cell(lat, lon, H3_RESOLUTION)


def to_geohash(lat: float, lon: float, precision: int = 7) -> str:
    return pgh.encode(lat, lon, precision=precision)


def shortlist_candidates(incident: Incident, ambulances: Iterable[Ambulance]) -> list[Ambulance]:
    now_ms = int(time.time() * 1000)
    active = [
        amb
        for amb in ambulances
        if amb.status == "AVAILABLE" and now_ms - amb.lastHeartbeatAt < 15000
    ]

    if not active:
        return []

    by_h3 = {amb.id: amb for amb in active}
    selected_ids: set[str] = set()
    for ring in range(0, 5):
        cells = h3.grid_disk(incident.pickupH3Cell, ring)
        for amb in active:
            if amb.h3Cell in cells:
                selected_ids.add(amb.id)
        if len(selected_ids) >= 12:
            break

    if len(selected_ids) < 6:
        for prefix_len in [7, 6, 5, 4]:
            prefix = incident.pickupGeohash[:prefix_len]
            for amb in active:
                if amb.geohash.startswith(prefix):
                    selected_ids.add(amb.id)
            if len(selected_ids) >= 12:
                break

    if not selected_ids:
        return active

    return [by_h3[amb_id] for amb_id in selected_ids if amb_id in by_h3]


def rank_candidates(incident: Incident, ambulances: Iterable[Ambulance]) -> list[DispatchCandidate]:
    ranked: list[DispatchCandidate] = []
    shortlisted = shortlist_candidates(incident, ambulances)
    live_etas, eta_source = _fetch_live_eta_minutes(incident, shortlisted)

    for amb in shortlisted:

        distance_km = haversine_km(incident.pickupLat, incident.pickupLon, amb.lat, amb.lon)
        eta_minutes = live_etas.get(amb.id, _build_fallback_eta_minutes(distance_km))
        reliability_penalty = (1 - amb.reliabilityScore) * 10

        score = (
            0.55 * eta_minutes
            + 0.2 * clinical_penalty(incident, amb)
            + 0.15 * reliability_penalty
        )

        ranked.append(
            DispatchCandidate(
                ambulanceId=amb.id,
                etaMinutes=round(eta_minutes, 2),
                score=round(score, 2),
                distanceKm=round(distance_km, 2),
                etaSource=eta_source if amb.id in live_etas else "approx",
            )
        )

    ranked.sort(key=lambda c: c.score)
    return ranked
