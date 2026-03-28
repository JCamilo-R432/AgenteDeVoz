-- Replication Setup SQL - AgenteDeVoz
-- Gap #12: Database Replication
-- Ejecutar en el nodo PRIMARY como superusuario

-- 1. Crear usuario de replicacion
CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD 'CHANGE_IN_PROD';

-- 2. Crear slots de replicacion fisica para cada replica
SELECT pg_create_physical_replication_slot('slot_replica1');
SELECT pg_create_physical_replication_slot('slot_replica2');

-- 3. Verificar slots
SELECT slot_name, slot_type, active, restart_lsn
FROM pg_replication_slots;

-- 4. Monitorear estado de replicacion
SELECT
    pid,
    usename,
    application_name,
    client_addr,
    state,
    sent_lsn,
    write_lsn,
    flush_lsn,
    replay_lsn,
    pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS lag_bytes,
    EXTRACT(EPOCH FROM (now() - reply_time)) AS lag_seconds
FROM pg_stat_replication;

-- 5. Estado del WAL receiver (ejecutar en REPLICA)
-- SELECT status, received_lsn, last_msg_send_time, last_msg_receipt_time
-- FROM pg_stat_wal_receiver;

-- 6. Promover replica a primario (en caso de failover - ejecutar en REPLICA)
-- SELECT pg_promote();

-- 7. Crear tabla de monitoreo de replicacion
CREATE TABLE IF NOT EXISTS replication_health_log (
    id SERIAL PRIMARY KEY,
    replica_name VARCHAR(50),
    lag_bytes BIGINT,
    lag_seconds FLOAT,
    state VARCHAR(20),
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- 8. Funcion para registrar metricas de replicacion
CREATE OR REPLACE FUNCTION log_replication_health()
RETURNS void AS $$
BEGIN
    INSERT INTO replication_health_log (replica_name, lag_bytes, lag_seconds, state)
    SELECT
        application_name,
        pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn),
        EXTRACT(EPOCH FROM (now() - reply_time)),
        state
    FROM pg_stat_replication;
END;
$$ LANGUAGE plpgsql;

-- Programar con pg_cron (si disponible):
-- SELECT cron.schedule('replication-health', '*/5 * * * *', 'SELECT log_replication_health()');
