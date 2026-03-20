-- CogMem Agent Schema Migration 001: Core Tables
-- Applied per-agent schema

CREATE TABLE IF NOT EXISTS memories (
    id VARCHAR(12) PRIMARY KEY,
    content TEXT NOT NULL,
    memory_type VARCHAR(20) DEFAULT 'active',
    memory_tier VARCHAR(20) DEFAULT 'episodic',
    emotional_weight FLOAT DEFAULT 0.5,
    tags TEXT[] DEFAULT '{}',
    entities TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_recalled TIMESTAMPTZ,
    recall_count INTEGER DEFAULT 0,
    sessions_since_recall INTEGER DEFAULT 0,
    source VARCHAR(100),
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS embeddings (
    memory_id VARCHAR(12) PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
    embedding vector(1536),
    model VARCHAR(100) DEFAULT 'text-embedding-3-small'
);

CREATE TABLE IF NOT EXISTS typed_edges (
    source_id VARCHAR(12) REFERENCES memories(id) ON DELETE CASCADE,
    target_id VARCHAR(12) REFERENCES memories(id) ON DELETE CASCADE,
    relationship VARCHAR(50) NOT NULL,
    strength FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (source_id, target_id, relationship)
);

CREATE TABLE IF NOT EXISTS cooccurrence_edges (
    source_id VARCHAR(12),
    target_id VARCHAR(12),
    strength FLOAT DEFAULT 1.0,
    observations INTEGER DEFAULT 1,
    last_observed TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (source_id, target_id)
);

CREATE TABLE IF NOT EXISTS key_value_store (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS session_events (
    id SERIAL PRIMARY KEY,
    session_id INTEGER,
    event_type VARCHAR(50),
    event_time TIMESTAMPTZ DEFAULT NOW(),
    content TEXT,
    content_preview VARCHAR(500),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_tier ON memories(memory_tier);
CREATE INDEX IF NOT EXISTS idx_session_events_time ON session_events(event_time);
