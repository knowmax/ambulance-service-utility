from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    RED = "RED"
    AMBER = "AMBER"
    GREEN = "GREEN"


class IncidentType(str, Enum):
    TRAUMA = "TRAUMA"
    CHEST_PAIN = "CHEST_PAIN"
    BREATHING = "BREATHING"
    UNCONSCIOUS = "UNCONSCIOUS"
    PREGNANCY = "PREGNANCY"
    OTHER = "OTHER"


class AmbulanceType(str, Enum):
    BLS = "BLS"
    ALS = "ALS"
    ICU = "ICU"


class AmbulanceStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    ENROUTE = "ENROUTE"
    AT_SCENE = "AT_SCENE"
    TRANSPORTING = "TRANSPORTING"
    OFFLINE = "OFFLINE"


class HeartbeatInput(BaseModel):
    type: AmbulanceType
    status: AmbulanceStatus
    lat: float
    lon: float
    reliabilityScore: float = Field(default=0.8, ge=0, le=1)


class SosInput(BaseModel):
    incidentType: IncidentType
    pickupLat: float
    pickupLon: float
    conscious: bool
    breathingNormally: bool
    severeBleeding: bool


class Ambulance(BaseModel):
    id: str
    type: AmbulanceType
    status: AmbulanceStatus
    lat: float
    lon: float
    h3Cell: str
    geohash: str
    lastHeartbeatAt: int
    reliabilityScore: float


class Incident(BaseModel):
    id: str
    incidentType: IncidentType
    severity: Severity
    pickupLat: float
    pickupLon: float
    pickupH3Cell: str
    pickupGeohash: str
    createdAt: int
    status: str
    assignedAmbulanceId: Optional[str] = None
    selectedHospitalId: Optional[str] = None
    selectedHospitalReason: Optional[str] = None


class DispatchCandidate(BaseModel):
    ambulanceId: str
    etaMinutes: float
    score: float
    distanceKm: float
    etaSource: Optional[str] = None


class DispatchAction(str, Enum):
    ACCEPT = "ACCEPT"
    DECLINE = "DECLINE"


class DispatchRespondInput(BaseModel):
    ambulanceId: str
    action: DispatchAction


class Hospital(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    emergencyAccepting: bool
    capabilities: list[str]
    handoverAvgMinutes: float = 15.0
    capacityLoad: float = Field(default=0.3, ge=0, le=1)
    insuranceNetworks: list[str] = Field(default_factory=list)


class HospitalRecommendation(BaseModel):
    hospitalId: str
    hospitalName: str
    distanceKm: float
    etaMinutes: float
    score: float
    estimatedCost: float
    matchedCapabilities: list[str]


class HospitalSelectInput(BaseModel):
    hospitalId: str
    reason: Optional[str] = None
