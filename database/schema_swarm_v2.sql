-- ============================================================
-- SWARM MEMORY V2 (shared inter-agent communication)
-- Replaces SQLite swarm_memory.db with PostgreSQL shared.* tables
-- Date: 2026-02-19
-- ============================================================

-- 1. PROJECTS (lightweight containers)
CREATE TABLE IF NOT EXISTS shared.swarm_projects (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    description TEXT,
    created_by VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    settings JSONB DEFAULT '{}'::jsonb
);

-- 2. MESSAGES (replaces swarm_memories)
CREATE TABLE IF NOT EXISTS shared.swarm_messages (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL REFERENCES shared.swarm_projects(id),
    content TEXT NOT NULL,
    summary VARCHAR(512),
    created_by VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    message_type VARCHAR(32) DEFAULT 'shared',
    tags TEXT[],
    emotional_weight FLOAT DEFAULT 0.5,
    recall_count INTEGER DEFAULT 0,
    last_recalled TIMESTAMPTZ,
    source_memory_id VARCHAR(64),
    search_vector TSVECTOR
);

CREATE INDEX IF NOT EXISTS idx_swarm_msg_project
    ON shared.swarm_messages(project_id);
CREATE INDEX IF NOT EXISTS idx_swarm_msg_created_by
    ON shared.swarm_messages(created_by);
CREATE INDEX IF NOT EXISTS idx_swarm_msg_created_at
    ON shared.swarm_messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_swarm_msg_type
    ON shared.swarm_messages(project_id, message_type);
CREATE INDEX IF NOT EXISTS idx_swarm_msg_tags
    ON shared.swarm_messages USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_swarm_msg_fts
    ON shared.swarm_messages USING GIN(search_vector);

-- Auto-maintain tsvector on insert/update
CREATE OR REPLACE FUNCTION shared.swarm_messages_search_trigger()
RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.summary, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.content, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_swarm_messages_search ON shared.swarm_messages;
CREATE TRIGGER trg_swarm_messages_search
    BEFORE INSERT OR UPDATE OF content, summary ON shared.swarm_messages
    FOR EACH ROW EXECUTE FUNCTION shared.swarm_messages_search_trigger();

-- 3. INBOX (unread message queue)
CREATE TABLE IF NOT EXISTS shared.swarm_inbox (
    id SERIAL PRIMARY KEY,
    recipient VARCHAR(50) NOT NULL,
    message_id VARCHAR(64) NOT NULL REFERENCES shared.swarm_messages(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    read_at TIMESTAMPTZ,
    notified_at TIMESTAMPTZ,
    UNIQUE(recipient, message_id)
);

-- Partial indexes for fast unread/unnotified queries
CREATE INDEX IF NOT EXISTS idx_swarm_inbox_unread
    ON shared.swarm_inbox(recipient) WHERE read_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_swarm_inbox_unnotified
    ON shared.swarm_inbox(recipient) WHERE notified_at IS NULL AND read_at IS NULL;
