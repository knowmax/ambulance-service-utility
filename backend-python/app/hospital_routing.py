from __future__ import annotations

from .dispatch import haversine_km
from .models import Hospital, HospitalRecommendation, Incident


def estimate_transport_cost(
    incident: Incident,
    distance_km: float,
    is_override: bool = False,
) -> dict:
    base_fare = 500.0
    distance_charge = distance_km * 25.0
    severity_surcharge = 0.0
    if incident.severity == "RED":
        severity_surcharge = 400.0
    elif incident.severity == "AMBER":
        severity_surcharge = 200.0

    override_surcharge = 250.0 if is_override else 0.0
    total = base_fare + distance_charge + severity_surcharge + override_surcharge
    return {
        "baseFare": round(base_fare, 2),
        "distanceCharge": round(distance_charge, 2),
        "severitySurcharge": round(severity_surcharge, 2),
        "overrideSurcharge": round(override_surcharge, 2),
        "total": round(total, 2),
    }


def required_capabilities(incident_type: str, severity: str) -> list[str]:
    req: list[str] = ["ER"]

    if incident_type == "TRAUMA":
        req.append("TRAUMA")
    elif incident_type == "CHEST_PAIN":
        req.append("CARDIAC")
    elif incident_type == "BREATHING":
        req.append("RESPIRATORY")
    elif incident_type == "PREGNANCY":
        req.append("OBGYN")
    elif incident_type == "UNCONSCIOUS":
        req.append("CRITICAL_CARE")

    if severity == "RED":
        req.append("ICU")

    return req


def recommend_hospitals(
    incident: Incident,
    hospitals: list[Hospital],
    insurance: str | None = None,
    top_n: int = 3,
) -> list[HospitalRecommendation]:
    required = required_capabilities(incident.incidentType, incident.severity)

    ranked: list[HospitalRecommendation] = []
    for hospital in hospitals:
        if not hospital.emergencyAccepting:
            continue

        matched = [cap for cap in required if cap in hospital.capabilities]
        capability_mismatch = len(required) - len(matched)

        # For RED incidents, only show clinically capable hospitals in recommendations.
        if incident.severity == "RED" and capability_mismatch > 0:
            continue

        distance_km = haversine_km(incident.pickupLat, incident.pickupLon, hospital.lat, hospital.lon)
        eta_minutes = max(2.0, (distance_km / 22.0) * 60.0)
        capacity_penalty = hospital.capacityLoad * 25
        capability_penalty = capability_mismatch * 20
        insurance_penalty = 0.0
        if insurance and insurance.upper() not in {item.upper() for item in hospital.insuranceNetworks}:
            insurance_penalty = 8.0

        score = (
            0.35 * eta_minutes
            + 0.20 * hospital.handoverAvgMinutes
            + 0.20 * capacity_penalty
            + 0.15 * capability_penalty
            + 0.10 * insurance_penalty
        )

        ranked.append(
            HospitalRecommendation(
                hospitalId=hospital.id,
                hospitalName=hospital.name,
                distanceKm=round(distance_km, 2),
                etaMinutes=round(eta_minutes, 2),
                score=round(score, 2),
                estimatedCost=estimate_transport_cost(incident, distance_km, is_override=False)["total"],
                matchedCapabilities=matched,
            )
        )

    ranked.sort(key=lambda rec: rec.score)
    return ranked[:top_n]


def evaluate_hospital_safety(incident: Incident, hospital: Hospital) -> dict:
    required = required_capabilities(incident.incidentType, incident.severity)
    missing = [cap for cap in required if cap not in hospital.capabilities]
    is_unsafe_for_red = incident.severity == "RED" and len(missing) > 0

    return {
        "requiredCapabilities": required,
        "missingCapabilities": missing,
        "isUnsafeForRed": is_unsafe_for_red,
    }
