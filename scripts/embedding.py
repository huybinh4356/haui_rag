# ============================================================
# BỘ CODE EMBEDDING - CÓ RESUME + DỪNG KHI HẾT QUOTA
# ============================================================

import os
import json
import time
import psycopg2
from psycopg2.extras import Json
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv
from google import genai
from google.genai import types


# ============================================================
# CẤU HÌNH
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "rag_haui")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")

if not GEMINI_API_KEY:
    raise ValueError("❌ Chưa có GEMINI_API_KEY trong .env")
if not DB_PASSWORD:
    raise ValueError("❌ Chưa có DB_PASSWORD trong .env")

http_options = types.HttpOptions(timeout=300000)
client = genai.Client(api_key=GEMINI_API_KEY, http_options=http_options)

INPUT_JSON_DIR = "./data/output_json"
PROGRESS_FILE = "./data/embedding_progress.json"
EMBEDDING_MODEL = "gemini-embedding-001"

SLEEP_BETWEEN_CHUNKS = 2.0   # Nghỉ giữa các chunk
MAX_RETRIES = 3              # Số lần retry khi gặp 429


# ============================================================
# QUẢN LÝ TIẾN ĐỘ
# ============================================================

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_index": 0, "success": 0, "fail": 0}


def save_progress(data):
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# EXCEPTION RIÊNG CHO RATE LIMIT
# ============================================================

class RateLimitError(Exception):
    pass


# ============================================================
# HÀM TẠO EMBEDDING
# ============================================================

def get_embedding(text, task_type="RETRIEVAL_DOCUMENT"):
    """
    - Trả về embedding nếu thành công.
    - Raise RateLimitError nếu hết quota (để dừng chương trình).
    - Trả về None nếu lỗi khác.
    """
    for attempt in range(MAX_RETRIES):
        try:
            result = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
                config=types.EmbedContentConfig(task_type=task_type),
            )
            return result.embeddings[0].values

        except Exception as e:
            error_msg = str(e)

            # --- Rate limit ---
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
                if attempt < MAX_RETRIES - 1:
                    wait = 30 * (attempt + 1)
                    print(f"      ⏸️  Rate limit. Chờ {wait}s...")
                    time.sleep(wait)
                else:
                    raise RateLimitError("Đã hết quota Gemini")
            # --- Lỗi khác ---
            else:
                wait = min(2 ** attempt, 15)
                print(f"      ⚠️  Lỗi: {error_msg[:100]}")
                time.sleep(wait)

    return None


# ============================================================
# KẾT NỐI DB
# ============================================================

def connect_db():
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    register_vector(conn)
    return conn


# ============================================================
# HÀM CHÍNH
# ============================================================

def load_chunks_to_postgres():
    print("=" * 60)
    print("🚀 BẮT ĐẦU EMBEDDING (CÓ RESUME)")
    print("=" * 60)

    conn = connect_db()
    print(f"✓ Đã kết nối DB: {DB_NAME}\n")

    # Đọc file JSON
    all_chunks_path = os.path.join(INPUT_JSON_DIR, "all_chunks.json")
    if not os.path.exists(all_chunks_path):
        print(f"❌ Không tìm thấy: {all_chunks_path}")
        conn.close()
        return

    with open(all_chunks_path, "r", encoding="utf-8") as f:
        all_chunks = json.load(f)

    total = len(all_chunks)

    # Đọc tiến độ
    progress = load_progress()
    start_index = progress.get("last_index", 0)

    print(f"📊 Tổng chunk: {total}")
    print(f"📍 Đã xử lý: {start_index}/{total}")
    print(f"⏳ Còn lại: {total - start_index}\n")

    if start_index >= total:
        print("🎉 Đã xử lý hết!")
        conn.close()
        return

    # --- Dọn dẹp bản ghi "mồ côi" từ lần chạy trước ---
    # (đảm bảo không duplicate nếu bị crash giữa chừng)
    with conn.cursor() as cur:
        cur.execute("""
            DELETE FROM documents 
            WHERE (metadata->>'chunk_index')::int >= %s
        """, (start_index,))
        deleted = cur.rowcount
        conn.commit()
        if deleted > 0:
            print(f"🧹 Đã xóa {deleted} bản ghi chưa hoàn chỉnh\n")

    # Kiểm tra số bản ghi trong DB
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documents")
        db_count = cur.fetchone()[0]
    print(f"🗄️  Bản ghi hiện có trong DB: {db_count}\n")

    # --- Bắt đầu xử lý ---
    success_count = 0
    fail_count = 0
    start_time = time.time()
    cur = conn.cursor()
    i = start_index  # Khai báo ngoài để dùng trong except

    try:
        for i in range(start_index, total):
            chunk = all_chunks[i]
            content = chunk["content"]
            metadata = chunk["metadata"]

            # Thêm chunk_index vào metadata để track
            metadata["chunk_index"] = i

            # Tạo embedding
            try:
                embedding = get_embedding(content)
            except RateLimitError:
                # ===== DỪNG LẠI =====
                print(f"\n🛑 HẾT QUOTA! Đã xử lý đến chunk {i}/{total}")
                conn.commit()

                progress["last_index"] = i
                progress["success"] = progress.get("success", 0) + success_count
                progress["fail"] = progress.get("fail", 0) + fail_count
                save_progress(progress)

                print(f"💾 Đã lưu tiến độ: {PROGRESS_FILE}")
                print(f"💡 Chạy lại sau để tiếp tục từ chunk {i + 1}")

                cur.close()
                conn.close()
                return

            # Lưu vào DB
            if embedding is None:
                fail_count += 1
            else:
                clean_meta = {}
                for k, v in metadata.items():
                    if v is None:
                        clean_meta[k] = ""
                    elif isinstance(v, (str, int, float, bool)):
                        clean_meta[k] = v
                    else:
                        clean_meta[k] = str(v)

                try:
                    cur.execute(
                        "INSERT INTO documents (content, metadata, embedding) VALUES (%s, %s, %s)",
                        (content, Json(clean_meta), embedding)
                    )
                    success_count += 1

                    # Commit + lưu tiến độ mỗi 20 chunk
                    if success_count % 20 == 0:
                        conn.commit()
                        progress["last_index"] = i + 1
                        progress["success"] = progress.get("success", 0) + success_count
                        progress["fail"] = progress.get("fail", 0) + fail_count
                        save_progress(progress)
                except Exception as e:
                    print(f"   ❌ Lỗi lưu chunk {i}: {e}")
                    conn.rollback()
                    fail_count += 1

            # In tiến độ
            if (i + 1) % 10 == 0 or i == start_index:
                elapsed = time.time() - start_time
                done = i + 1 - start_index
                eta = (elapsed / done) * (total - i - 1) if done > 0 else 0
                print(f"[{i+1}/{total}] ✓ {success_count} | ✗ {fail_count} | ETA: {eta/60:.1f} phút")

            time.sleep(SLEEP_BETWEEN_CHUNKS)

        # ===== HOÀN THÀNH TẤT CẢ =====
        conn.commit()
        progress["last_index"] = total
        progress["success"] = progress.get("success", 0) + success_count
        progress["fail"] = progress.get("fail", 0) + fail_count
        save_progress(progress)

        print("\n" + "=" * 60)
        print("🎉 HOÀN THÀNH TẤT CẢ")
        print("=" * 60)
        print(f"✓ Thành công: {success_count}")
        print(f"✗ Thất bại: {fail_count}")
        print(f"⏱️  Thời gian: {(time.time() - start_time)/60:.1f} phút")

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents")
            print(f"🔍 Tổng bản ghi trong DB: {cur.fetchone()[0]}")

    except KeyboardInterrupt:
        print(f"\n⚠️  Người dùng dừng (Ctrl+C) tại chunk {i}")
        conn.commit()
        progress["last_index"] = i
        progress["success"] = progress.get("success", 0) + success_count
        progress["fail"] = progress.get("fail", 0) + fail_count
        save_progress(progress)
        print(f"💾 Đã lưu tiến độ tại chunk {i}")

    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


# ============================================================
# TEST TRUY VẤN
# ============================================================

def test_search(query, top_k=3):
    print(f"\n🔍 Câu hỏi: {query}")
    print("-" * 60)

    conn = connect_db()
    query_embedding = get_embedding(query, task_type="RETRIEVAL_QUERY")

    if query_embedding is None:
        print("❌ Không thể tạo embedding")
        conn.close()
        return

    with conn.cursor() as cur:
        cur.execute("""
            SELECT content, metadata, embedding <=> %s::vector AS distance
            FROM documents
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """, (query_embedding, query_embedding, top_k))
        results = cur.fetchall()

    for i, (content, metadata, distance) in enumerate(results, 1):
        print(f"\n📌 Kết quả {i} (distance: {distance:.4f}):")
        print(f"   Mã văn bản: {metadata.get('ma_van_ban', 'N/A')}")
        print(f"   Điều: {metadata.get('dieu', 'N/A')} | Khoản: {metadata.get('khoan', 'N/A')}")
        print(f"   Nội dung: {content[:200]}...")

    conn.close()


# ============================================================
# CHẠY
# ============================================================

if __name__ == "__main__":
    load_chunks_to_postgres()
    # test_search("Điều kiện tốt nghiệp thạc sĩ là gì?")