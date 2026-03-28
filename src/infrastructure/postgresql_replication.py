"""
PostgreSQL Replication - AgenteDeVoz
Gap #12: Configuracion especifica de replicacion PostgreSQL

Genera configuracion para primary y replicas, slots de replicacion,
y comandos de administracion pg_basebackup.
"""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PostgreSQLConfig:
    host: str
    port: int = 5432
    database: str = "agentevoz"
    replication_user: str = "replicator"
    replication_password: str = "CHANGE_ME"
    max_wal_senders: int = 5
    wal_level: str = "replica"          # replica | logical
    wal_keep_size: str = "1GB"
    max_replication_slots: int = 5
    synchronous_commit: str = "on"      # on | local | remote_write | remote_apply | off
    application_name: str = "agentevoz_replica"


class PostgreSQLReplicationConfigurator:
    """
    Genera configuracion de replicacion para PostgreSQL 14+.
    Soporta streaming replication y logical replication.
    """

    def __init__(self, config: PostgreSQLConfig):
        self.config = config

    def generate_primary_config(self) -> str:
        """Genera postgresql.conf para el nodo primario."""
        cfg = self.config
        return f"""# PostgreSQL Primary Configuration - AgenteDeVoz
# Generado automaticamente - Gap #12 HA/Replication

# Conexiones
listen_addresses = '*'
port = {cfg.port}
max_connections = 200

# Replicacion
wal_level = {cfg.wal_level}
max_wal_senders = {cfg.max_wal_senders}
wal_keep_size = {cfg.wal_keep_size}
max_replication_slots = {cfg.max_replication_slots}
synchronous_commit = {cfg.synchronous_commit}
hot_standby = on

# Archivado WAL (habilitar con servidor de archivos)
# archive_mode = on
# archive_command = 'cp %p /var/lib/postgresql/wal_archive/%f'

# Performance
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100

# Logging
log_min_duration_statement = 1000
log_checkpoints = on
log_connections = on
log_replication_commands = on
"""

    def generate_replica_config(self, primary_host: str, replica_name: str = "replica1") -> str:
        """Genera postgresql.conf para un nodo replica."""
        cfg = self.config
        return f"""# PostgreSQL Replica Configuration - AgenteDeVoz
# Nodo: {replica_name}

listen_addresses = '*'
port = {cfg.port}
max_connections = 200

# Modo hot standby - permite consultas de lectura
hot_standby = on
hot_standby_feedback = on

# Recovery target - conectar al primario
primary_conninfo = 'host={primary_host} port={cfg.port} user={cfg.replication_user} password={cfg.replication_password} application_name={replica_name}'
primary_slot_name = 'slot_{replica_name}'

# Performance
shared_buffers = 256MB
effective_cache_size = 1GB

# Logging
log_min_duration_statement = 1000
log_connections = on
"""

    def generate_pg_hba_primary(self, replica_hosts: List[str]) -> str:
        """Genera pg_hba.conf para el primario."""
        lines = [
            "# pg_hba.conf - Primary",
            "# TYPE  DATABASE        USER            ADDRESS                 METHOD",
            "local   all             all                                     trust",
            "host    all             all             127.0.0.1/32            scram-sha-256",
            "host    all             all             ::1/128                 scram-sha-256",
            "",
            "# Replication slots",
        ]
        for host in replica_hosts:
            lines.append(
                f"host    replication     {self.config.replication_user}    {host}/32    scram-sha-256"
            )
        return "\n".join(lines)

    def generate_replication_slot_sql(self, slot_name: str) -> str:
        """SQL para crear un slot de replicacion permanente."""
        return f"SELECT pg_create_physical_replication_slot('{slot_name}');"

    def generate_basebackup_command(
        self, primary_host: str, output_dir: str = "/var/lib/postgresql/14/replica"
    ) -> str:
        """Genera el comando pg_basebackup para inicializar una replica."""
        cfg = self.config
        return (
            f"pg_basebackup "
            f"-h {primary_host} "
            f"-p {cfg.port} "
            f"-U {cfg.replication_user} "
            f"-D {output_dir} "
            f"-P -Xs -R --checkpoint=fast"
        )

    def generate_replication_monitoring_sql(self) -> Dict[str, str]:
        """SQL queries para monitorear replicacion."""
        return {
            "lag_bytes": """
SELECT
    application_name,
    client_addr,
    state,
    pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS lag_bytes,
    EXTRACT(EPOCH FROM (now() - reply_time)) AS lag_seconds
FROM pg_stat_replication;
""",
            "slots": """
SELECT slot_name, active, pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS retained_bytes
FROM pg_replication_slots;
""",
            "replica_status": """
SELECT
    status,
    received_lsn,
    last_msg_send_time,
    last_msg_receipt_time
FROM pg_stat_wal_receiver;
""",
        }
