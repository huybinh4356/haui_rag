-- Migration 002: Tạo bảng messages lưu trữ lịch sử tin nhắn
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    request_id VARCHAR(100),
    query_type VARCHAR(50),
    latency_ms INTEGER,
    fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
    citations JSONB,
    metadata JSONB
);
