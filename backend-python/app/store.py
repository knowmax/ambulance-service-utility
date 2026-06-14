from __future__ import annotations

from dataclasses import dataclass, field

from .models import Ambulance, Hospital, Incident


@dataclass
class Store:
    ambulances: dict[str, Ambulance] = field(default_factory=dict)
    incidents: dict[str, Incident] = field(default_factory=dict)
    dispatches: dict[str, dict] = field(default_factory=dict)
    hospitals: dict[str, Hospital] = field(default_factory=dict)


store = Store()
