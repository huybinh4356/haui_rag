-- Migration 005: Tạo các index tối ưu hóa truy vấn hội thoại, tin nhắn và logs
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_created ON messages(conversation_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_request_logs_created_at ON request_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_request_logs_conversation ON request_logs(conversation_id);
CREATE INDEX IF NOT EXISTS idx_feedback_message ON feedback(message_id);
