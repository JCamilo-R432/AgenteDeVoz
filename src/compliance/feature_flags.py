"""
Feature Flags Manager - AgenteDeVoz
Gap #40: Sistema de feature flags para releases graduales

Permite:
- Activar/desactivar features sin deploy
- Rollout gradual por porcentaje de usuarios
- Flags por usuario especifico (whitelist/blacklist)
- Rollback instantaneo si hay problemas
- Audit log de todos los cambios
"""
import hashlib
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class FlagStatus(Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    ROLLOUT = "rollout"  # Activo solo para un % de usuarios


@dataclass
class FeatureFlag:
    name: str
    description: str
    enabled: bool
    rollout_percentage: float  # 0.0 a 100.0
    created_at: datetime
    updated_at: datetime
    created_by: str
    tags: List[str] = field(default_factory=list)
    allowed_users: Set[str] = field(default_factory=set)
    blocked_users: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def status(self) -> str:
        if not self.enabled:
            return FlagStatus.DISABLED.value
        if self.rollout_percentage < 100.0:
            return FlagStatus.ROLLOUT.value
        return FlagStatus.ENABLED.value

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "rollout_percentage": self.rollout_percentage,
            "status": self.status(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "tags": self.tags,
            "allowed_users_count": len(self.allowed_users),
            "metadata": self.metadata,
        }


class FeatureFlagManager:
    """
    Gestor de feature flags con rollout gradual y audit log.

    Uso tipico:
        flags = FeatureFlagManager()
        flags.create_flag("nuevo_modelo_tts", enabled=False, rollout_percentage=0)

        # Rollout gradual: empezar con 10%
        flags.set_rollout("nuevo_modelo_tts", 10.0, updated_by="devops")

        # Verificar en codigo
        if flags.is_enabled("nuevo_modelo_tts", user_id="user_123"):
            use_new_tts()

        # Aumentar a 50%
        flags.set_rollout("nuevo_modelo_tts", 50.0, updated_by="devops")

        # Rollback inmediato si hay problemas
        flags.update_flag("nuevo_modelo_tts", enabled=False)
    """

    def __init__(self, redis_client=None):
        self._flags: Dict[str, FeatureFlag] = {}
        self._audit_log: List[Dict] = []
        self._redis = redis_client
        self._load_default_flags()

    def create_flag(
        self,
        name: str,
        description: str = "",
        enabled: bool = False,
        rollout_percentage: float = 100.0,
        created_by: str = "system",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
    ) -> FeatureFlag:
        """
        Crea un nuevo feature flag.

        Args:
            name: Nombre unico del flag (snake_case recomendado)
            description: Descripcion del feature
            enabled: Estado inicial (False por defecto para seguridad)
            rollout_percentage: Porcentaje de usuarios que veran el feature (0-100)
            created_by: Usuario que crea el flag
        """
        if name in self._flags:
            raise ValueError(f"Flag '{name}' ya existe. Usar update_flag() para modificar.")

        if not 0.0 <= rollout_percentage <= 100.0:
            raise ValueError("rollout_percentage debe estar entre 0.0 y 100.0")

        now = datetime.utcnow()
        flag = FeatureFlag(
            name=name,
            description=description,
            enabled=enabled,
            rollout_percentage=rollout_percentage,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            tags=tags or [],
            metadata=metadata or {},
        )

        self._flags[name] = flag
        self._log_audit(name, "created", {"enabled": enabled, "rollout": rollout_percentage}, created_by)
        logger.info(f"Feature flag creado: '{name}' (enabled={enabled}, rollout={rollout_percentage}%)")
        return flag

    def is_enabled(self, flag_name: str, user_id: Optional[str] = None) -> bool:
        """
        Verifica si un feature flag esta activo para un usuario.

        Logica de evaluacion (en orden):
        1. Si el flag no existe -> False
        2. Si el flag esta disabled -> False
        3. Si el usuario esta en blocked_users -> False
        4. Si el usuario esta en allowed_users -> True
        5. Si rollout_percentage < 100% -> decision deterministica por hash del user_id
        6. Si rollout_percentage = 100% -> True

        Args:
            flag_name: Nombre del flag
            user_id: ID del usuario (para rollout gradual)
        """
        flag = self._flags.get(flag_name)

        # Flag no existe
        if not flag:
            logger.debug(f"Flag '{flag_name}' no encontrado - retornando False")
            return False

        # Flag deshabilitado globalmente
        if not flag.enabled:
            return False

        # Usuario bloqueado explicitamente
        if user_id and user_id in flag.blocked_users:
            return False

        # Usuario en whitelist (siempre activo)
        if user_id and user_id in flag.allowed_users:
            return True

        # Rollout parcial: decision deterministica
        if flag.rollout_percentage < 100.0:
            if not user_id:
                # Sin user_id, usar el porcentaje global
                return flag.rollout_percentage > 0
            return self._is_in_rollout(user_id, flag_name, flag.rollout_percentage)

        return True

    def _is_in_rollout(self, user_id: str, flag_name: str, percentage: float) -> bool:
        """
        Determina si un usuario cae en el porcentaje de rollout.
        Usa MD5 para asignacion deterministica (mismo usuario = misma decision).
        """
        hash_input = f"{user_id}:{flag_name}".encode()
        hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
        # Mapear a rango 0-100 para comparar con porcentaje
        user_bucket = (hash_value % 10000) / 100.0  # 0.00 a 99.99
        return user_bucket < percentage

    def update_flag(self, flag_name: str, updated_by: str = "system", **kwargs) -> bool:
        """
        Actualiza uno o mas atributos de un flag.

        Args:
            **kwargs: Campos a actualizar (enabled, rollout_percentage, description, tags, metadata)
        """
        flag = self._flags.get(flag_name)
        if not flag:
            return False

        updatable = {"enabled", "rollout_percentage", "description", "tags", "metadata"}
        changes = {}

        for key, value in kwargs.items():
            if key in updatable:
                if key == "rollout_percentage" and not 0.0 <= value <= 100.0:
                    raise ValueError("rollout_percentage debe estar entre 0.0 y 100.0")
                old_value = getattr(flag, key)
                setattr(flag, key, value)
                changes[key] = {"old": old_value, "new": value}

        if changes:
            flag.updated_at = datetime.utcnow()
            self._log_audit(flag_name, "updated", changes, updated_by)
            logger.info(f"Flag '{flag_name}' actualizado por '{updated_by}': {changes}")

        return True

    def set_rollout(self, flag_name: str, percentage: float, updated_by: str) -> bool:
        """
        Actualiza el porcentaje de rollout de un flag.

        Args:
            percentage: Nuevo porcentaje (0.0 a 100.0)
            updated_by: Usuario que realiza el cambio (para audit)
        """
        return self.update_flag(flag_name, updated_by=updated_by, rollout_percentage=percentage)

    def add_allowed_user(self, flag_name: str, user_id: str) -> bool:
        """Agrega un usuario a la whitelist del flag (siempre activo para el)."""
        flag = self._flags.get(flag_name)
        if not flag:
            return False
        flag.allowed_users.add(user_id)
        flag.blocked_users.discard(user_id)  # Remover de blacklist si estaba
        self._log_audit(flag_name, "user_allowed", {"user_id": user_id}, "system")
        return True

    def block_user(self, flag_name: str, user_id: str) -> bool:
        """Agrega un usuario a la blacklist del flag (siempre inactivo para el)."""
        flag = self._flags.get(flag_name)
        if not flag:
            return False
        flag.blocked_users.add(user_id)
        flag.allowed_users.discard(user_id)
        self._log_audit(flag_name, "user_blocked", {"user_id": user_id}, "system")
        return True

    def get_flag(self, flag_name: str) -> Optional[FeatureFlag]:
        """Retorna un flag por nombre."""
        return self._flags.get(flag_name)

    def list_flags(self, tag: Optional[str] = None) -> List[Dict]:
        """Lista todos los flags, opcionalmente filtrados por tag."""
        flags = self._flags.values()
        if tag:
            flags = [f for f in flags if tag in f.tags]
        return [f.to_dict() for f in flags]

    def get_audit_log(self, flag_name: Optional[str] = None) -> List[Dict]:
        """
        Retorna el audit log de cambios en flags.

        Args:
            flag_name: Si se especifica, filtra por flag. Si no, retorna todo.
        """
        if flag_name:
            return [e for e in self._audit_log if e["flag"] == flag_name]
        return self._audit_log

    def _log_audit(
        self,
        flag_name: str,
        action: str,
        details: Dict,
        performed_by: str,
    ) -> None:
        """Registra un cambio en el audit log."""
        self._audit_log.append({
            "flag": flag_name,
            "action": action,
            "details": details,
            "performed_by": performed_by,
            "timestamp": datetime.utcnow().isoformat(),
        })
        # Mantener audit log acotado (ultimos 10000 eventos)
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-5000:]

    def _load_default_flags(self) -> None:
        """Carga flags predeterminados del sistema AgenteDeVoz."""
        defaults = [
            {
                "name": "use_llm_intent_classifier",
                "description": "Usar LLM (GPT-4o-mini/Claude Haiku) para clasificacion de intenciones en lugar de keywords",
                "enabled": True,
                "rollout_percentage": 100.0,
                "tags": ["nlp", "llm"],
            },
            {
                "name": "google_stt_primary",
                "description": "Usar Google Cloud STT como motor primario (False = Whisper primario)",
                "enabled": True,
                "rollout_percentage": 100.0,
                "tags": ["stt", "speech"],
            },
            {
                "name": "whatsapp_channel",
                "description": "Canal WhatsApp activo para atencion al cliente",
                "enabled": True,
                "rollout_percentage": 100.0,
                "tags": ["channel", "whatsapp"],
            },
            {
                "name": "ab_testing_active",
                "description": "Framework A/B testing activo para experimentos",
                "enabled": False,
                "rollout_percentage": 0.0,
                "tags": ["ab_testing", "experimental"],
            },
            {
                "name": "wake_word_detection",
                "description": "Deteccion de wake word antes de activar STT completo",
                "enabled": False,
                "rollout_percentage": 0.0,
                "tags": ["voice", "experimental"],
            },
            {
                "name": "business_intelligence_v2",
                "description": "Nuevo motor de BI con segmentacion avanzada",
                "enabled": False,
                "rollout_percentage": 0.0,
                "tags": ["analytics", "experimental"],
            },
        ]

        for flag_data in defaults:
            try:
                self.create_flag(**flag_data, created_by="system")
            except ValueError:
                pass  # Flag ya existe
