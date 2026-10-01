"""Trinh giam sat log va phien su dung truc tiep theo thoi gian thuc cho haui_rag."""

import os
import sys
import time
from pathlib import Path

# Thiet lap UTF-8 output cho console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT_DIR / "data" / "logs"
LOG_FILE = LOG_DIR / "haui_rag.log"


def monitor_logs() -> None:
    """Theo doi va in truc tiep cac dong log moi nhat tu haui_rag.log."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if not LOG_FILE.exists():
        LOG_FILE.write_text("", encoding="utf-8")

    print("-" * 70)
    print("  HAUI RAG - LIVE LOG & SESSION MONITOR (Giam sat hoat dong va loi)")
    print(f"  Tep nhat ky: {LOG_FILE}")
    print("  Cua so nay chay song song de theo doi truy van, thoi gian va loi.")
    print("-" * 70)
    print("\n[San sang theo doi nhat ky he thong...]")

    # Doc 30 dong cuoi cung neu da co du lieu
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            for line in lines[-25:]:
                print(line, end="")
    except Exception as e:
        print(f"[Canh bao] Khong doc duoc log ban dau: {e}")

    # Che do live tail (giong tail -f)
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if line:
                    # In dong log
                    print(line, end="", flush=True)
                else:
                    time.sleep(0.3)
    except KeyboardInterrupt:
        print("\n[Da dung giam sat log]")


if __name__ == "__main__":
    monitor_logs()
