---
trigger: always_on
---

# Quy tắc bảo mật

## 1. Quản lý API key

### BẮT BUỘC

- Lưu tất cả key trong file `.env`
- Đọc bằng `os.getenv()` hoặc `python-dotenv`
- Thêm `.env` vào `.gitignore`
- Tạo file `.env.example` (không chứa giá trị thật) để chia sẻ

### CẤM

- Hard-code key trong code
- Commit `.env` lên Git
- Log key ra console
- Chia sẻ key qua chat, email không mã hóa

### Ví dụ ĐÚNG

```python
from dotenv import load_dotenv
import os

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("Chưa có GEMINI_API_KEY trong .env")
```

## Bảo vệ dữ liệu cá nhân

-Số điện thoại, email, CMND/CCCD
-Địa chỉ nhà
-Điểm số, kết quả học tập cá nhân
-Thông tin tài khoản ngân hàng

```python
import re

def mask_pii(text: str) -> str:
    """Che dấu thông tin cá nhân trong log."""
    # Số điện thoại VN
    text = re.sub(r'\b0\d{9,10}\b', '***PHONE***', text)
    # Email
    text = re.sub(r'\S+@\S+\.\S+', '***EMAIL***', text)
    # CMND/CCCD
    text = re.sub(r'\b\d{9,12}\b', '***ID***', text)
    return text
```

## Chống Prompt Injection

-**Danh sách pattern nguy hiểm**

```python
DANGEROUS_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "bỏ qua hướng dẫn",
    "bỏ qua tất cả",
    "system prompt",
    "you are now",
    "act as",
    "pretend to be",
    "đóng vai",
    "quên đi",
    "forget everything",
]

def is_safe_query(query: str) -> bool:
    """Kiểm tra câu hỏi có chứa prompt injection không."""
    query_lower = query.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in query_lower:
            return False
    return True
```

## Database Security
-**Connection**
-Cho phép sử dụng kết nối từ localhost hoặc IP nội bộ 
-Không expose port 5432 ra internet 
-**Queries**
-Luôn dùng parameter queries


```
python 
# ĐÚNG
cur.execute("SELECT * FROM documents WHERE id = %s", (doc_id,))

# SAI (SQL Injection)
cur.execute(f"SELECT * FROM documents WHERE id = {doc_id}")

```

-**Backup**
-Backup định kỳ bằng pg_dump
-Lưu backup ở nơi khác và không cần mã hóa


##Phân Quyền##
-**Guest**: Chỉ cho phép xem câu hỏi mẫu 
-**Sinh viên**: Chat, tra cứu văn bản công khai
-**Giảng viên** : Chat, tra cứu vẳn bản, tải biểu mẫu,upload văn bản 
-**Admin** : Tất cả các quyền và cho phép quản lý user và auditlog

##Audit Log

-**Bắt Buộc* ghi log 
- Mọi câu hỏi của người dùng
- Câu trả lời của AI 
- Thời gian và IP
- Feedback
-**Format** 
```
json 
{
  "timestamp": "2026-09-24T14:30:00Z",
  "user_id": "hashed_user_id",
  "question": "Điều kiện tốt nghiệp?",
  "answer_hash": "sha256_hash",
  "sources": ["41/QĐ-ĐHCN"],
  "response_time_ms": 3200,
  "feedback": null
}
```

