"""Module quản lý và thực thi Database Migrations cho dự án haui_rag.

Quản lý việc tạo bảng ứng dụng (conversations, messages, request_logs, feedback)
một cách có kiểm soát thông qua bảng lưu vết `schema_migrations`.
"""

import logging
from pathlib import Path
from typing import Optional
import psycopg2

from haui_rag.db.connection import connect_db

logger = logging.getLogger("haui_rag.db.migrator")

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "migrations"


def init_migrations_table(conn: psycopg2.extensions.connection) -> None:
    """Khởi tạo bảng schema_migrations nếu chưa tồn tại."""
    sql = """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version VARCHAR(100) PRIMARY KEY,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def get_applied_migrations(conn: psycopg2.extensions.connection) -> set[str]:
    """Lấy danh sách các migration đã được áp dụng trong database."""
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations;")
        rows = cur.fetchall()
        return {r[0] for r in rows}


def run_migrations(migrations_path: Optional[Path] = None) -> list[str]:
    """
    Quét và thực thi tất cả các file SQL migration chưa được áp dụng theo thứ tự.

    Args:
        migrations_path: Đường dẫn thư mục chứa các file .sql (mặc định là migrations/).

    Returns:
        list[str]: Danh sách tên các migration vừa được áp dụng thành công.
    """
    target_dir = migrations_path or MIGRATIONS_DIR
    if not target_dir.exists():
        logger.warning("Thư mục migration không tồn tại: %s", target_dir)
        return []

    sql_files = sorted(target_dir.glob("*.sql"))
    if not sql_files:
        logger.info("Không tìm thấy file migration nào trong %s", target_dir)
        return []

    conn = connect_db()
    applied_now: list[str] = []

    try:
        init_migrations_table(conn)
        already_applied = get_applied_migrations(conn)

        for file_path in sql_files:
            filename = file_path.name
            if filename in already_applied:
                continue

            logger.info("Đang áp dụng migration: %s", filename)
            sql_content = file_path.read_text(encoding="utf-8")

            with conn.cursor() as cur:
                cur.execute(sql_content)
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s);",
                    (filename,),
                )
            conn.commit()
            applied_now.append(filename)
            logger.info("Áp dụng thành công migration: %s", filename)

        if not applied_now:
            logger.info("Tất cả migrations đã được áp dụng trước đó. Hệ thống cập nhật.")

        return applied_now
    except Exception as e:
        conn.rollback()
        logger.error("Lỗi khi thực thi migrations: %s", e, exc_info=True)
        raise
    finally:
        if not conn.closed:
            conn.close()


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    res = run_migrations()
    logger.info("Da thuc thi xong %d migrations: %s", len(res), res)
