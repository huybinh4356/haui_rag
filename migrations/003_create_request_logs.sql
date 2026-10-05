-- Migration 003: Tạo bảng request_logs theo dõi kỹ thuật và độ trễ
CREATE TABLE IF NOT EXISTS request_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id VARCHAR(100) NOT NULL,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    endpoint VARCHAR(100),
    status_code INTEGER,
    embedding_latency_ms INTEGER,
    retrieval_latency_ms INTEGER,
    rerank_latency_ms INTEGER,
    generation_latency_ms INTEGER,
    total_latency_ms INTEGER,
    fallback_used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB
);
