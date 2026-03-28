-- ============================================================
-- Esquema de Base de Datos - Agente de Voz
-- PostgreSQL 15+
-- Ejecutar como: psql -U postgres -d agentevoz -f database_schema.sql
-- ============================================================

-- Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ────────────────────────────────────────────────────────────
-- Tabla: users
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    phone           VARCHAR(15) NOT NULL,
    email           VARCHAR(255),
    full_name       VARCHAR(255),
    crm_id          VARCHAR(100),
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    auth_attempts   SMALLINT    NOT NULL DEFAULT 0,
    blocked_until   TIMESTAMP,
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone   ON users(phone);
CREATE INDEX        IF NOT EXISTS idx_users_crm_id  ON users(crm_id);
CREATE INDEX        IF NOT EXISTS idx_users_email   ON users(email);

-- ────────────────────────────────────────────────────────────
-- Tabla: conversations (particionada por mes)
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id                  UUID        NOT NULL DEFAULT gen_random_uuid(),
    user_id             UUID        REFERENCES users(id),
    session_id          VARCHAR(100) NOT NULL,
    channel             VARCHAR(20) NOT NULL DEFAULT 'phone',
    phone_from          VARCHAR(15),
    phone_to            VARCHAR(15),
    status              VARCHAR(20) NOT NULL DEFAULT 'active',
    transcript          TEXT,
    resolution_status   VARCHAR(20),
    csat_score          SMALLINT    CHECK (csat_score BETWEEN 1 AND 5),
    duration            INTEGER,
    escalated_to        VARCHAR(100),
    created_at          TIMESTAMP   NOT NULL DEFAULT NOW(),
    ended_at            TIMESTAMP,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Crear partición para el año actual (agregar una por mes en producción)
CREATE TABLE IF NOT EXISTS conversations_2026
    PARTITION OF conversations
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_session
    ON conversations(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_user
    ON conversations(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_status
    ON conversations(status, created_at);

-- ────────────────────────────────────────────────────────────
-- Tabla: tickets
-- ────────────────────────────────────────────────────────────
CREATE SEQUENCE IF NOT EXISTS ticket_seq START 1;

CREATE TABLE IF NOT EXISTS tickets (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_number       VARCHAR(20) NOT NULL,
    user_id             UUID        REFERENCES users(id),
    conversation_id     UUID,
    category            VARCHAR(50) NOT NULL DEFAULT 'otro',
    description         TEXT        NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'ABIERTO',
    priority            VARCHAR(10) NOT NULL DEFAULT 'MEDIA',
    channel             VARCHAR(20) NOT NULL DEFAULT 'voice',
    assigned_to         VARCHAR(100),
    resolution_notes    TEXT,
    sla_deadline        TIMESTAMP,
    created_at          TIMESTAMP   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP   NOT NULL DEFAULT NOW(),
    closed_at           TIMESTAMP,
    CONSTRAINT chk_ticket_status   CHECK (status   IN ('ABIERTO','EN_PROCESO','RESUELTO','CERRADO','REABIERTO')),
    CONSTRAINT chk_ticket_priority CHECK (priority IN ('BAJA','MEDIA','ALTA','URGENTE'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_tickets_number  ON tickets(ticket_number);
CREATE INDEX        IF NOT EXISTS idx_tickets_user    ON tickets(user_id);
CREATE INDEX        IF NOT EXISTS idx_tickets_status  ON tickets(status);
CREATE INDEX        IF NOT EXISTS idx_tickets_priority_status ON tickets(priority, status);
CREATE INDEX        IF NOT EXISTS idx_tickets_created ON tickets(created_at);

-- ────────────────────────────────────────────────────────────
-- Tabla: intents
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS intents (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID,
    turn_number         SMALLINT        NOT NULL,
    intent_type         VARCHAR(50)     NOT NULL,
    confidence          NUMERIC(4,3),
    user_text           TEXT            NOT NULL,
    agent_response      TEXT,
    entities_json       JSONB           DEFAULT '{}',
    fallback            BOOLEAN         NOT NULL DEFAULT FALSE,
    processing_ms       INTEGER,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_intents_conversation ON intents(conversation_id);
CREATE INDEX IF NOT EXISTS idx_intents_type         ON intents(intent_type);
CREATE INDEX IF NOT EXISTS idx_intents_created      ON intents(created_at);

-- ────────────────────────────────────────────────────────────
-- Tabla: escalations
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS escalations (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id              VARCHAR(100),
    conversation_id         UUID,
    type                    VARCHAR(50) NOT NULL DEFAULT 'escalation',
    reason                  VARCHAR(255),
    conversation_summary    TEXT,
    transferred_to          VARCHAR(100),
    timestamp               TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_escalations_session    ON escalations(session_id);
CREATE INDEX IF NOT EXISTS idx_escalations_timestamp  ON escalations(timestamp);

-- ────────────────────────────────────────────────────────────
-- Tabla: callbacks
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS callbacks (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    phone           VARCHAR(15) NOT NULL,
    preferred_time  VARCHAR(100),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    scheduled_at    TIMESTAMP   NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMP
);

-- ────────────────────────────────────────────────────────────
-- Tabla: integrations_log
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS integrations_log (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id     UUID,
    service_name        VARCHAR(50) NOT NULL,
    method              VARCHAR(10) NOT NULL,
    endpoint            VARCHAR(255) NOT NULL,
    request_payload     JSONB,
    response_payload    JSONB,
    status_code         SMALLINT,
    success             BOOLEAN     NOT NULL,
    duration_ms         INTEGER,
    error_message       TEXT,
    created_at          TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_int_log_service   ON integrations_log(service_name);
CREATE INDEX IF NOT EXISTS idx_int_log_created   ON integrations_log(created_at);
CREATE INDEX IF NOT EXISTS idx_int_log_success   ON integrations_log(success);

-- ────────────────────────────────────────────────────────────
-- Tabla: audit_log (inmutable)
-- ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id              BIGSERIAL   PRIMARY KEY,
    action          VARCHAR(50) NOT NULL,
    table_name      VARCHAR(50),
    record_id       VARCHAR(100),
    user_id         UUID        REFERENCES users(id),
    agent_id        VARCHAR(100),
    ip_address      INET,
    session_id      VARCHAR(100),
    old_values_json JSONB,
    new_values_json JSONB,
    created_at      TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_user      ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action    ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_created   ON audit_log(created_at);

-- Hacer audit_log inmutable
CREATE OR REPLACE RULE no_update_audit AS ON UPDATE TO audit_log DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_delete_audit AS ON DELETE TO audit_log DO INSTEAD NOTHING;

-- ────────────────────────────────────────────────────────────
-- Función y triggers para updated_at automático
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_users_updated_at   ON users;
DROP TRIGGER IF EXISTS update_tickets_updated_at ON tickets;

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tickets_updated_at
    BEFORE UPDATE ON tickets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ────────────────────────────────────────────────────────────
-- Datos iniciales (seed) para desarrollo
-- ────────────────────────────────────────────────────────────
INSERT INTO users (phone, email, full_name, crm_id)
VALUES
    ('3101234567', 'juan.perez@test.com',  'Juan Pérez García',   'HUB-00001'),
    ('3209876543', 'maria.lopez@test.com', 'María López Martínez','HUB-00002')
ON CONFLICT (phone) DO NOTHING;
