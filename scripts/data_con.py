import json
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from pgvector.psycopg2 import register_vector

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# 1. Kết nối tới database
conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=os.getenv("DB_PORT", "5432"),
    database=os.getenv("DB_NAME", "rag_haui"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "")
)

# 2. Đăng ký kiểu dữ liệu vector cho psycopg2
register_vector(conn)

# 3. Dữ liệu cần thêm (vector giả định)
chunk_content = "Điều 5. Đối tượng và điều kiện dự tuyển..."
chunk_metadata = {"dieu": "5", "khoan": "1"}
chunk_embedding = [0.1] * 768  # Vector 768 chiều

# 4. Chèn dữ liệu vào bảng
with conn.cursor() as cur:
    cur.execute(
        "INSERT INTO documents (content, metadata, embedding) VALUES (%s, %s, %s)",
        (chunk_content, json.dumps(chunk_metadata), chunk_embedding)
    )
conn.commit()
print("Đã thêm dữ liệu thành công!")