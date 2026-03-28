import logging
from typing import Any, Dict, List, Optional

from config.settings import settings


class Database:
    """
    Capa de acceso a PostgreSQL.

    Usa psycopg2 directamente para el MVP. En producción
    considera migrar a SQLAlchemy async para mejor rendimiento.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.connection = None
        self._connect()

    def _connect(self) -> None:
        """Establece la conexión con PostgreSQL."""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            self.connection = psycopg2.connect(
                settings.DATABASE_URL,
                cursor_factory=RealDictCursor,
                connect_timeout=10,
            )
            self.connection.autocommit = False
            self.logger.info("Conexión a PostgreSQL establecida.")

        except ImportError:
            self.logger.error("psycopg2 no instalado. Ejecuta: pip install psycopg2-binary")
            raise
        except Exception as e:
            self.logger.error(f"Error conectando a PostgreSQL: {e}")
            raise

    def _ensure_connection(self) -> None:
        """Verifica y reconecta si la conexión se perdió."""
        try:
            if self.connection and self.connection.closed:
                self.logger.warning("Conexión cerrada. Reconectando...")
                self._connect()
        except Exception as e:
            self.logger.error(f"Error verificando conexión: {e}")
            self._connect()

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def insert(self, table: str, data: Dict[str, Any]) -> Optional[str]:
        """
        Inserta un registro en la tabla.

        Args:
            table: Nombre de la tabla (se valida contra lista de tablas permitidas).
            data: Dict con columna → valor.

        Returns:
            ID del registro insertado como string, o None si falla.
        """
        self._validate_table_name(table)
        self._ensure_connection()

        try:
            cursor = self.connection.cursor()
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["%s"] * len(data))
            query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING id"

            cursor.execute(query, list(data.values()))
            record = cursor.fetchone()
            self.connection.commit()
            cursor.close()

            record_id = str(record["id"]) if record else None
            self.logger.debug(f"INSERT {table} | id: {record_id}")
            return record_id

        except Exception as e:
            self.logger.error(f"Error INSERT {table}: {e}")
            self.connection.rollback()
            return None

    def find_one(self, table: str, criteria: Dict[str, Any]) -> Optional[Dict]:
        """
        Busca el primer registro que coincida con los criterios.

        Args:
            table: Nombre de la tabla.
            criteria: Dict con columna → valor para el WHERE.

        Returns:
            Dict con el registro o None si no se encuentra.
        """
        self._validate_table_name(table)
        self._ensure_connection()

        try:
            cursor = self.connection.cursor()
            conditions = " AND ".join([f"{k} = %s" for k in criteria.keys()])
            query = f"SELECT * FROM {table} WHERE {conditions} LIMIT 1"

            cursor.execute(query, list(criteria.values()))
            result = cursor.fetchone()
            cursor.close()

            return dict(result) if result else None

        except Exception as e:
            self.logger.error(f"Error SELECT {table}: {e}")
            return None

    def find_all(
        self,
        table: str,
        criteria: Optional[Dict[str, Any]] = None,
        order_by: str = "created_at DESC",
        limit: int = 100,
    ) -> List[Dict]:
        """
        Busca todos los registros que coincidan con los criterios.

        Args:
            table: Nombre de la tabla.
            criteria: Dict con columna → valor para el WHERE (opcional).
            order_by: Cláusula ORDER BY.
            limit: Máximo de registros a retornar.

        Returns:
            Lista de dicts con los registros encontrados.
        """
        self._validate_table_name(table)
        self._ensure_connection()

        try:
            cursor = self.connection.cursor()

            if criteria:
                conditions = " AND ".join([f"{k} = %s" for k in criteria.keys()])
                query = f"SELECT * FROM {table} WHERE {conditions} ORDER BY {order_by} LIMIT {limit}"
                cursor.execute(query, list(criteria.values()))
            else:
                query = f"SELECT * FROM {table} ORDER BY {order_by} LIMIT {limit}"
                cursor.execute(query)

            results = cursor.fetchall()
            cursor.close()

            return [dict(row) for row in results]

        except Exception as e:
            self.logger.error(f"Error SELECT ALL {table}: {e}")
            return []

    def update(
        self,
        table: str,
        criteria: Dict[str, Any],
        data: Dict[str, Any],
    ) -> bool:
        """
        Actualiza los registros que coincidan con los criterios.

        Args:
            table: Nombre de la tabla.
            criteria: Dict con columna → valor para el WHERE.
            data: Dict con columna → nuevo valor.

        Returns:
            True si se actualizó al menos un registro.
        """
        self._validate_table_name(table)
        self._ensure_connection()

        try:
            cursor = self.connection.cursor()
            set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
            conditions = " AND ".join([f"{k} = %s" for k in criteria.keys()])
            query = f"UPDATE {table} SET {set_clause} WHERE {conditions}"

            cursor.execute(query, list(data.values()) + list(criteria.values()))
            affected = cursor.rowcount
            self.connection.commit()
            cursor.close()

            self.logger.debug(f"UPDATE {table} | rows affected: {affected}")
            return affected > 0

        except Exception as e:
            self.logger.error(f"Error UPDATE {table}: {e}")
            self.connection.rollback()
            return False

    def execute_raw(self, query: str, params: Optional[tuple] = None) -> Optional[List[Dict]]:
        """
        Ejecuta una consulta SQL arbitraria (solo para operaciones internas autorizadas).

        Args:
            query: SQL a ejecutar (usar solo con queries hardcoded, nunca con input del usuario).
            params: Parámetros para la consulta.

        Returns:
            Lista de resultados o None.
        """
        self._ensure_connection()
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)

            if cursor.description:
                results = [dict(row) for row in cursor.fetchall()]
            else:
                results = []

            self.connection.commit()
            cursor.close()
            return results

        except Exception as e:
            self.logger.error(f"Error executing raw query: {e}")
            self.connection.rollback()
            return None

    def get_customer_by_phone(self, phone: str) -> Optional[Dict]:
        """
        Busca un cliente por número de teléfono.

        Normaliza el número antes de buscar (elimina espacios, guiones, código de país).
        Retorna None si el cliente no está registrado.

        Args:
            phone: Número de teléfono en cualquier formato.

        Returns:
            Dict con datos del cliente o None.
        """
        import re

        # Normalizar: conservar solo dígitos y el + inicial
        digits = re.sub(r"[^\d]", "", phone)
        # Intentar con el número tal como está y variaciones comunes
        variants = [digits]
        if digits.startswith("57") and len(digits) == 12:   # Colombia +57
            variants.append(digits[2:])                      # sin código de país
        if len(digits) == 10:                                # local colombiano
            variants.append("57" + digits)                   # con código de país

        self._ensure_connection()
        try:
            cursor = self.connection.cursor()
            placeholders = ", ".join(["%s"] * len(variants))
            query = (
                f"SELECT u.*, s.plan_id, s.status AS subscription_status "
                f"FROM users u "
                f"LEFT JOIN subscriptions s ON s.user_id = u.id AND s.status = 'active' "
                f"WHERE REGEXP_REPLACE(u.phone, '[^0-9]', '', 'g') IN ({placeholders}) "
                f"LIMIT 1"
            )
            cursor.execute(query, variants)
            result = cursor.fetchone()
            cursor.close()

            if result:
                self.logger.info(f"Cliente encontrado para teléfono {phone}: {result.get('id')}")
            else:
                self.logger.info(f"Cliente no encontrado para teléfono {phone}")

            return dict(result) if result else None

        except Exception as e:
            self.logger.error(f"Error buscando cliente por teléfono: {e}")
            return None

    def close(self) -> None:
        """Cierra la conexión a la base de datos."""
        if self.connection and not self.connection.closed:
            self.connection.close()
            self.logger.info("Conexión a PostgreSQL cerrada.")

    # ── Validación de seguridad ───────────────────────────────────────────────

    ALLOWED_TABLES = {
        "users", "conversations", "tickets", "intents",
        "escalations", "audit_log", "integrations_log", "callbacks",
    }

    def _validate_table_name(self, table: str) -> None:
        """Valida que el nombre de tabla esté en la lista de tablas permitidas."""
        if table not in self.ALLOWED_TABLES:
            raise ValueError(
                f"Tabla '{table}' no permitida. "
                f"Tablas válidas: {', '.join(sorted(self.ALLOWED_TABLES))}"
            )
