---
trigger: always_on
---

# Hướng dẫn phong cách Python

## Chuẩn chung

- Tuân thủ **PEP 8**
- Độ dài dòng tối đa: **100 ký tự**
- Indent: **4 spaces** (không dùng tab)
- Encoding: **UTF-8**

## Đặt tên

- **Biến, hàm:** `snake_case` (ví dụ: `get_embedding`, `ma_van_ban`)
- **Class:** `PascalCase` (ví dụ: `RateLimitError`, `DocumentChunk`)
- **Hằng số:** `UPPER_SNAKE_CASE` (ví dụ: `MAX_RETRIES`, `DB_HOST`)
- **Private:** prefix `_` (ví dụ: `_internal_function`)

## Type hints (BẮT BUỘC)

```python
def get_embedding(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float] | None:
```

## Docstring

-**BẮT BUỘC** viết docstring cho mọi hàm puclic
-Dùng chuẩn **Google style**
-Format: Mô tả -> Args -> Returns -> Raises

```python
def search_documents(query: str, top_k: int = 5) -> list[dict]:
    """
    Tìm top_k chunks liên quan nhất trong PostgreSQL.
    
    Args:
        query: Câu hỏi của người dùng
        top_k: Số lượng chunks cần lấy
        
    Returns:
        List các dict chứa content, metadata, distance
        
    Raises:
        ConnectionError: Khi không kết nối được database
    """
```

## Logging

-**KHÔNG** dùng print()
-**BẮT BUỘC** dùng logging
-Mỗi file :

```
python 
logger = logging.getLogger(__name__)
```

-Dùng đúng câos độ : debug, info, warning, error, critical
-Khi log lỗi : thêm `exc_info=True`

```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"Đang xử lý chunk {idx}/{total}")
logger.warning(f"Rate limit, chờ {wait}s")
logger.error(f"Lỗi kết nối DB: {e}", exc_info=True)```

## Xử lý lỗi 
##**BẮT BUỘC** dùng `try`...`except` cho mọi thao tác I/O
-Phải raise exception cụ thể (không dùng Exception chung)
-Phải log lỗi trước khi raise
-##**CẤM** dùng `except:pass`(nuốt lỗi)
-Phải đóng resource trong finally 

``` python 
 #  ĐÚNG
try:
    conn = psycopg2.connect(...)
except psycopg2.OperationalError as e:
    logger.error(f"Không kết nối được DB: {e}", exc_info=True)
    raise ConnectionError("Database không khả dụng") from e
finally:
    if conn:
        conn.close()

#  SAI
try:
    conn = psycopg2.connect(...)
except:
    pass
```

## Import

-Sắp xếp theo thứ tự, mỗi nhóm cách nhau 1 dòng trống:
1.Stdlib(os,json,time)
2.Third-party (psycopg2, google.genai)
3.Local (from utils import ...)

## Constants

-Khai báo ở đầu file, sau imports
-Nhóm theo chủ đề, có comment

```
python 
# Cấu hình Database
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

# Cấu hình Gemini
EMBEDDING_MODEL = "gemini-embedding-001"
LLM_MODEL = "gemini-2.0-flash"
```

## Comment

-Chỉ comment khi cần(logic phức tạp, workaround)
-Không comment những gì code đã rõ
-Dùng  tiếng Việt cho comment nghiệp vụ

``` python
"""Module docstring - mô tả ngắn gọn module làm gì."""

# 1. Imports (stdlib → third-party → local)
import os
import psycopg2

# 2. Constants
DB_HOST = "localhost"

# 3. Logger
logger = logging.getLogger(__name__)

# 4. Helper functions
def helper(): ...

# 5. Main functions
def main(): ...

# 6. Entry point
if __name__ == "__main__":
    main()
```
