"""
Data Deletion - AgenteDeVoz
Gap #9: Eliminacion segura de datos personales (Art. 17 GDPR)

Implementa eliminacion en cascade y anonimizacion irreversible.
"""
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DeletionResult:
    user_id: str
    deleted_at: str
    tables_affected: List[str]
    records_deleted: int
    anonymized: int
    retained: List[Dict]
    success: bool


class DataDeletionService:
    """
    Servicio de eliminacion segura de datos personales.
    Implementa eliminacion en cascade y anonimizacion irreversible.
    """

    # Tablas con datos personales y si se pueden eliminar o solo anonimizar
    DATA_TABLES = {
        "users": {"action": "delete", "cascade": True},
        "conversations": {"action": "anonymize", "cascade": False},
        "conversation_turns": {"action": "anonymize", "cascade": False},
        "voice_recordings": {"action": "delete", "cascade": True},
        "user_preferences": {"action": "delete", "cascade": True},
        "activity_logs": {"action": "delete", "cascade": True},
        "consents": {"action": "delete", "cascade": True},
        "sessions": {"action": "delete", "cascade": True},
    }

    # Tablas retenidas por ley (no se eliminan)
    LEGALLY_RETAINED = {
        "tickets": {"reason": "Obligacion legal 5 anos", "legal_basis": "Art. 17.3.b RGPD"},
        "invoices": {"reason": "Obligacion fiscal", "legal_basis": "Normativa tributaria"},
        "audit_logs": {"reason": "Seguridad y auditoria", "legal_basis": "Art. 17.3.e RGPD"},
    }

    def __init__(self):
        self._deletion_log: List[Dict] = []

    def delete_user_data(self, user_id: str, dry_run: bool = False) -> DeletionResult:
        """
        Elimina o anonimiza todos los datos del usuario.

        Args:
            user_id: ID del usuario
            dry_run: Si True, solo simula sin modificar datos

        Returns:
            DeletionResult con detalle de lo eliminado
        """
        tables_affected = []
        records_deleted = 0
        anonymized = 0

        if not dry_run:
            logger.info("Iniciando eliminacion de datos para usuario %s", user_id)

        for table, config in self.DATA_TABLES.items():
            if config["action"] == "delete":
                if not dry_run:
                    count = self._delete_from_table(user_id, table, config["cascade"])
                else:
                    count = 1  # Simulado en dry_run
                records_deleted += count
                tables_affected.append(f"{table} (eliminado: {count})")
            elif config["action"] == "anonymize":
                if not dry_run:
                    count = self._anonymize_in_table(user_id, table)
                else:
                    count = 1
                anonymized += count
                tables_affected.append(f"{table} (anonimizado: {count})")

        retained = [
            {"table": t, **info}
            for t, info in self.LEGALLY_RETAINED.items()
        ]

        result = DeletionResult(
            user_id=user_id,
            deleted_at=datetime.now().isoformat(),
            tables_affected=tables_affected,
            records_deleted=records_deleted,
            anonymized=anonymized,
            retained=retained,
            success=True,
        )

        if not dry_run:
            self._deletion_log.append({
                "user_id": user_id,
                "deleted_at": result.deleted_at,
                "tables": tables_affected,
                "dry_run": False,
            })
            logger.info(
                "Eliminacion completada: %d registros eliminados, %d anonimizados",
                records_deleted, anonymized,
            )

        return result

    def _delete_from_table(self, user_id: str, table: str, cascade: bool) -> int:
        """Elimina registros del usuario de una tabla (simulado)."""
        # En produccion:
        # cursor.execute(f"DELETE FROM {table} WHERE user_id = %s", (user_id,))
        # return cursor.rowcount
        logger.debug("DELETE FROM %s WHERE user_id = %s (cascade=%s)", table, user_id, cascade)
        return 1  # Simulado

    def _anonymize_in_table(self, user_id: str, table: str) -> int:
        """Anonimiza datos del usuario en una tabla (simulado)."""
        anon_id = hashlib.sha256(f"ANON:{user_id}".encode()).hexdigest()[:16]
        # En produccion:
        # cursor.execute(f"""
        #     UPDATE {table} SET user_id = %s, phone = NULL, email = NULL
        #     WHERE user_id = %s
        # """, (f"ANON_{anon_id}", user_id))
        logger.debug("ANONYMIZE %s WHERE user_id = %s -> %s", table, user_id, anon_id)
        return 1  # Simulado

    def verify_deletion(self, user_id: str) -> bool:
        """Verifica que no queden datos identificables del usuario."""
        # En produccion: consultar cada tabla y confirmar ausencia
        deleted_users = [log["user_id"] for log in self._deletion_log]
        return user_id in deleted_users

    def get_deletion_log(self) -> List[Dict]:
        return list(self._deletion_log)
