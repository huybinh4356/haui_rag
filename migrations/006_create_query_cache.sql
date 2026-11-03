-- Migration 006: Tạo bảng query_cache lưu trữ câu hỏi đã tra cứu và câu trả lời để tái sử dụng lâu dài
CREATE TABLE IF NOT EXISTS query_cache (
    cache_key VARCHAR(64) PRIMARY KEY,
    normalized_query TEXT NOT NULL,
    original_query TEXT NOT NULL,
    top_k INTEGER NOT NULL DEFAULT 5,
    answer TEXT NOT NULL,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    query_type VARCHAR(50),
    fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
    citation_audit JSONB,
    hit_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_hit_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_query_cache_normalized ON query_cache(normalized_query, top_k);
CREATE INDEX IF NOT EXISTS idx_query_cache_hit_count ON query_cache(hit_count DESC, last_hit_at DESC);

