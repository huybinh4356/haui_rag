"""Giao dien tro chuyen Terminal toi gian cho Tro ly AI Quy che HaUI."""

import logging
import os
import sys
import warnings
from pathlib import Path

# Tat cac thong bao warning khong can thiet
warnings.filterwarnings("ignore")
logging.getLogger().setLevel(logging.ERROR)
logging.getLogger("haui_rag").setLevel(logging.ERROR)

# Thiet lap UTF-8 output cho console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# Them thu muc goc va src vao sys.path
ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from haui_rag.config import ACTIVE_LLM_MODEL, DEFAULT_TOP_K, validate_config
from haui_rag.core.rag_pipeline import rag_query_stream
from haui_rag.logger import setup_logger

# Khoi tao logger de toan bo thong tin phien & loi duoc ghi vao data/logs/haui_rag.log
logger = setup_logger("haui_rag")
for handler in logger.handlers:
    # An log info tren man hinh chat de giao dien sach dep, log van vao file cho monitor window
    if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
        handler.setLevel(logging.ERROR)


def run_terminal_chat() -> None:
    """Vong lap hoi dap toi gian tren terminal."""
    try:
        validate_config()
    except Exception as e:
        print(f"[Loi cau hinh]: {e}")
        return

    print("-" * 50)
    print(f"Tro ly AI Quy che HaUI ({ACTIVE_LLM_MODEL})")
    print("Go cau hoi va nhan Enter (Go 'q' de thoat, 'cls' de xoa man hinh)")
    print("-" * 50)

    while True:
        try:
            user_input = input("\nBan: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[Tam biet!]")
            break

        if not user_input:
            continue

        lower = user_input.lower()
        if lower in ["q", "exit", "quit"]:
            print("[Tam biet!]")
            break

        if lower in ["cls", "clear"]:
            os.system("cls" if sys.platform == "win32" else "clear")
            print(f"Tro ly AI Quy che HaUI ({ACTIVE_LLM_MODEL}) - Go 'q' de thoat")
            print("-" * 50)
            continue

        try:
            logger.info("Terminal Session - Nguoi dung hoi: '%s'", user_input)
            sources, stream_gen, meta = rag_query_stream(user_input, top_k=DEFAULT_TOP_K)

            print("\nHaUI: ", end="", flush=True)
            for token in stream_gen:
                sys.stdout.write(token)
                sys.stdout.flush()
            print()

            # Hien thi nguon ngan gon 1 dong o cuoi
            if sources:
                citations = []
                seen = set()
                for s in sources:
                    cit = s.get("citation", "").strip()
                    if cit and cit not in seen:
                        seen.add(cit)
                        citations.append(cit)
                if citations:
                    print(f"\n[Nguon: {' | '.join(citations[:3])}]")

            logger.info(
                "Terminal Session - Hoan thanh tra loi (Retrieval: %d ms, Chunks: %d)",
                meta.get("retrieval_time_ms", 0),
                len(sources),
            )
            print("-" * 50)

        except Exception as e:
            logger.error("Terminal Session - Loi xu ly cau hoi '%s': %s", user_input, e, exc_info=True)
            print(f"\n[Loi]: {e}")
            print("-" * 50)


if __name__ == "__main__":
    run_terminal_chat()
