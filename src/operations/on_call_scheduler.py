"""
On-Call Scheduler - AgenteDeVoz
Gap #16: Programacion de turnos on-call y escalado automatico

Gestiona rotaciones de guardia y escalado segun horarios.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ShiftType(Enum):
    PRIMARY = "primary"      # Ingeniero principal de guardia
    SECONDARY = "secondary"  # Respaldo si primario no responde
    MANAGER = "manager"      # Escalado a manager


@dataclass
class Engineer:
    engineer_id: str
    name: str
    email: str
    phone: str
    timezone: str = "America/Bogota"
    team: str = "platform"


@dataclass
class OnCallShift:
    shift_id: str
    engineer: Engineer
    shift_type: ShiftType
    start_time: datetime
    end_time: datetime
    active: bool = True

    def is_current(self) -> bool:
        now = datetime.now()
        return self.active and self.start_time <= now <= self.end_time


@dataclass
class EscalationPolicy:
    policy_id: str
    name: str
    levels: List[ShiftType] = field(
        default_factory=lambda: [ShiftType.PRIMARY, ShiftType.SECONDARY, ShiftType.MANAGER]
    )
    ack_timeout_minutes: int = 15    # minutos antes de escalar al siguiente nivel


class OnCallScheduler:
    """
    Gestiona turnos de guardia y politicas de escalado.
    Identifica quien esta on-call en un momento dado.
    """

    def __init__(self):
        self._engineers: Dict[str, Engineer] = {}
        self._shifts: List[OnCallShift] = []
        self._policies: Dict[str, EscalationPolicy] = {}
        self._shift_counter = 0
        self._default_policy = EscalationPolicy(
            policy_id="default",
            name="Escalado default AgenteDeVoz",
        )
        logger.info("OnCallScheduler inicializado")

    def register_engineer(self, engineer: Engineer) -> None:
        self._engineers[engineer.engineer_id] = engineer
        logger.info("Ingeniero registrado: %s (%s)", engineer.name, engineer.team)

    def add_shift(
        self,
        engineer_id: str,
        shift_type: ShiftType,
        start_time: datetime,
        end_time: datetime,
    ) -> Optional[OnCallShift]:
        engineer = self._engineers.get(engineer_id)
        if not engineer:
            logger.error("Ingeniero no encontrado: %s", engineer_id)
            return None

        self._shift_counter += 1
        shift = OnCallShift(
            shift_id=f"SHIFT-{self._shift_counter:04d}",
            engineer=engineer,
            shift_type=shift_type,
            start_time=start_time,
            end_time=end_time,
        )
        self._shifts.append(shift)
        return shift

    def create_weekly_rotation(
        self,
        engineer_ids: List[str],
        start_date: datetime,
        weeks: int = 4,
        shift_type: ShiftType = ShiftType.PRIMARY,
    ) -> List[OnCallShift]:
        """Crea rotacion semanal distribuyendo ingenieros en orden."""
        shifts = []
        for week in range(weeks):
            engineer_id = engineer_ids[week % len(engineer_ids)]
            week_start = start_date + timedelta(weeks=week)
            week_end = week_start + timedelta(weeks=1) - timedelta(seconds=1)
            shift = self.add_shift(engineer_id, shift_type, week_start, week_end)
            if shift:
                shifts.append(shift)
        return shifts

    def get_current_oncall(self, shift_type: ShiftType = ShiftType.PRIMARY) -> Optional[Engineer]:
        """Retorna el ingeniero on-call actual para el tipo de turno indicado."""
        now = datetime.now()
        for shift in self._shifts:
            if shift.shift_type == shift_type and shift.is_current():
                return shift.engineer
        return None

    def get_escalation_chain(self, policy_id: str = "default") -> List[Engineer]:
        """Retorna la cadena de escalado en orden de contacto."""
        policy = self._policies.get(policy_id, self._default_policy)
        chain = []
        for shift_type in policy.levels:
            engineer = self.get_current_oncall(shift_type)
            if engineer and engineer not in chain:
                chain.append(engineer)
        return chain

    def get_shifts_for_engineer(
        self, engineer_id: str, include_past: bool = False
    ) -> List[OnCallShift]:
        now = datetime.now()
        return [
            s for s in self._shifts
            if s.engineer.engineer_id == engineer_id
            and (include_past or s.end_time >= now)
        ]

    def get_schedule_summary(self, days_ahead: int = 14) -> List[Dict]:
        cutoff = datetime.now() + timedelta(days=days_ahead)
        upcoming = [
            s for s in self._shifts
            if s.end_time >= datetime.now() and s.start_time <= cutoff
        ]
        upcoming.sort(key=lambda s: s.start_time)
        return [
            {
                "shift_id": s.shift_id,
                "engineer": s.engineer.name,
                "type": s.shift_type.value,
                "start": s.start_time.isoformat(),
                "end": s.end_time.isoformat(),
                "current": s.is_current(),
            }
            for s in upcoming
        ]

    def register_policy(self, policy: EscalationPolicy) -> None:
        self._policies[policy.policy_id] = policy

    def get_current_on_call_summary(self) -> Dict:
        return {
            "primary": (e := self.get_current_oncall(ShiftType.PRIMARY)) and {
                "name": e.name, "email": e.email, "phone": e.phone
            },
            "secondary": (e2 := self.get_current_oncall(ShiftType.SECONDARY)) and {
                "name": e2.name, "email": e2.email, "phone": e2.phone
            },
            "manager": (m := self.get_current_oncall(ShiftType.MANAGER)) and {
                "name": m.name, "email": m.email
            },
            "checked_at": datetime.now().isoformat(),
        }
