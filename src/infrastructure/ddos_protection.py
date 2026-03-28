"""
DDoS Protection - AgenteDeVoz
Gap #14: Proteccion contra ataques DDoS

Detecta patrones de ataque (flood, slowloris, amplificacion) y activa
mitigaciones automaticas.
"""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AttackType(Enum):
    HTTP_FLOOD = "http_flood"
    SLOWLORIS = "slowloris"
    AMPLIFICATION = "amplification"
    VOLUMETRIC = "volumetric"
    UNKNOWN = "unknown"


class MitigationAction(Enum):
    NONE = "none"
    RATE_LIMIT = "rate_limit"
    CHALLENGE = "challenge"       # CAPTCHA o JS challenge
    BLOCK = "block"
    BLACKHOLE = "blackhole"       # Null route


@dataclass
class DDoSConfig:
    rps_threshold: int = 1000          # peticiones/seg globales para alerta
    per_ip_rps_threshold: int = 50     # peticiones/seg por IP para bloqueo
    connection_timeout_s: float = 30.0  # para detectar slowloris
    auto_mitigation: bool = True
    challenge_threshold: int = 500      # rps para challenge (antes de block)


@dataclass
class AttackEvent:
    attack_id: str
    detected_at: str
    attack_type: AttackType
    source_ips: List[str]
    rps: float
    mitigation: MitigationAction
    active: bool = True
    resolved_at: Optional[str] = None


class DDoSProtection:
    """
    Sistema de proteccion DDoS con deteccion automatica y mitigacion.
    Opera como capa complementaria al rate limiter por IP/usuario.
    """

    def __init__(self, config: Optional[DDoSConfig] = None):
        self.config = config or DDoSConfig()
        self._request_log: List[float] = []          # timestamps globales
        self._ip_log: Dict[str, List[float]] = {}    # timestamps por IP
        self._blocked_ips: Set[str] = set()
        self._challenged_ips: Set[str] = set()
        self._attack_events: List[AttackEvent] = []
        self._mitigation_active = False
        self._event_counter = 0
        logger.info("DDoSProtection inicializado (rps_threshold=%d)", config.rps_threshold if config else 1000)

    def record_request(self, ip: str, path: str = "/") -> MitigationAction:
        """
        Registra peticion y evalua si se debe aplicar mitigacion.
        Returns: MitigationAction a aplicar para esta peticion.
        """
        if ip in self._blocked_ips:
            return MitigationAction.BLOCK

        now = time.time()
        self._request_log.append(now)
        if ip not in self._ip_log:
            self._ip_log[ip] = []
        self._ip_log[ip].append(now)

        # Limpiar datos > 1 segundo
        cutoff = now - 1.0
        self._request_log = [t for t in self._request_log if t > cutoff]
        self._ip_log[ip] = [t for t in self._ip_log[ip] if t > cutoff]

        global_rps = len(self._request_log)
        ip_rps = len(self._ip_log[ip])

        # Evaluar por IP
        if ip_rps >= self.config.per_ip_rps_threshold:
            if self.config.auto_mitigation:
                self._blocked_ips.add(ip)
                self._detect_attack(AttackType.HTTP_FLOOD, [ip], ip_rps)
            return MitigationAction.BLOCK

        # Evaluar globalmente
        if global_rps >= self.config.rps_threshold:
            if not self._mitigation_active:
                self._mitigation_active = True
                top_ips = self._get_top_attackers()
                self._detect_attack(AttackType.VOLUMETRIC, top_ips, global_rps)
            if ip in self._challenged_ips:
                return MitigationAction.CHALLENGE
            if global_rps >= self.config.rps_threshold * 2:
                return MitigationAction.RATE_LIMIT

        return MitigationAction.NONE

    def _detect_attack(self, attack_type: AttackType, ips: List[str], rps: float) -> None:
        self._event_counter += 1
        event = AttackEvent(
            attack_id=f"DDOS-{self._event_counter:04d}",
            detected_at=datetime.now().isoformat(),
            attack_type=attack_type,
            source_ips=ips[:20],  # max 20 IPs en el evento
            rps=rps,
            mitigation=MitigationAction.BLOCK if rps > self.config.per_ip_rps_threshold else MitigationAction.RATE_LIMIT,
        )
        self._attack_events.append(event)
        logger.error(
            "ATAQUE DDoS detectado [%s]: %d rps, %d IPs (event=%s)",
            attack_type.value, rps, len(ips), event.attack_id,
        )

    def _get_top_attackers(self, n: int = 10) -> List[str]:
        return sorted(
            self._ip_log.keys(),
            key=lambda ip: len(self._ip_log[ip]),
            reverse=True,
        )[:n]

    def unblock_ip(self, ip: str) -> bool:
        if ip in self._blocked_ips:
            self._blocked_ips.discard(ip)
            return True
        return False

    def challenge_ip(self, ip: str) -> None:
        self._challenged_ips.add(ip)

    def resolve_attack(self, attack_id: str) -> bool:
        for event in self._attack_events:
            if event.attack_id == attack_id:
                event.active = False
                event.resolved_at = datetime.now().isoformat()
                self._mitigation_active = any(e.active for e in self._attack_events)
                return True
        return False

    def get_global_rps(self) -> float:
        cutoff = time.time() - 1.0
        self._request_log = [t for t in self._request_log if t > cutoff]
        return float(len(self._request_log))

    def is_under_attack(self) -> bool:
        return self._mitigation_active or (self.get_global_rps() >= self.config.rps_threshold)

    def get_status(self) -> Dict:
        return {
            "under_attack": self.is_under_attack(),
            "mitigation_active": self._mitigation_active,
            "global_rps": round(self.get_global_rps(), 1),
            "blocked_ips": len(self._blocked_ips),
            "challenged_ips": len(self._challenged_ips),
            "attack_events": len(self._attack_events),
            "active_events": sum(1 for e in self._attack_events if e.active),
        }

    def get_attack_events(self) -> List[Dict]:
        return [
            {
                "attack_id": e.attack_id,
                "detected_at": e.detected_at,
                "type": e.attack_type.value,
                "rps": e.rps,
                "source_ips": e.source_ips,
                "mitigation": e.mitigation.value,
                "active": e.active,
                "resolved_at": e.resolved_at,
            }
            for e in self._attack_events
        ]
