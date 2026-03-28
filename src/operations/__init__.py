"""Modulo de operaciones: gestion de incidentes y on-call."""
from .incident_manager import IncidentManager, Incident, IncidentSeverity
from .incident_response import IncidentResponsePlaybook
from .on_call_scheduler import OnCallScheduler

__all__ = [
    "IncidentManager",
    "Incident",
    "IncidentSeverity",
    "IncidentResponsePlaybook",
    "OnCallScheduler",
]
