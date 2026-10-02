"""
Script test thuc chien he thong RAG HaUI.
Gui cau hoi that vao pipeline, hien thi ket qua day du,
do thoi gian phan hoi, danh gia chat luong truc tiep.

Chay: python scripts/live_test.py
"""

import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from haui_rag.config import ACTIVE_LLM_MODEL, DEFAULT_TOP_K, validate_config
from haui_rag.core.rag_pipeline import rag_query

TEST_CASES = [
    {
        "category": "Tot nghiep",
        "question": "Dieu kien de duoc xet tot nghiep dai hoc tai HaUI la gi?",
        "expect_keywords": ["tin chi", "diem", "tot nghiep"],
    },
    {
        "category": "Hoc phi",
        "question": "Sinh vien HaUI duoc mien giam hoc phi trong nhung truong hop nao?",
        "expect_keywords": ["mien", "giam", "hoc phi"],
    },
    {
        "category": "Ky luat",
        "question": "Sinh vien vi pham quy che thi cu bi xu ly nhu the nao?",
        "expect_keywords": ["ky luat", "thi", "vi pham"],
    },
    {
        "category": "Hoc bong",
        "question": "Tieu chuan xet hoc bong khuyen khich hoc tap tai HaUI?",
        "expect_keywords": ["hoc bong", "diem", "xet"],
    },
    {
        "category": "Thac si",
        "question": "thac si",
        "expect_keywords": ["thac si"],
    },
    {
        "category": "Bao luu",
        "question": "Sinh vien duoc bao luu ket qua hoc tap toi da bao nhieu nam?",
        "expect_keywords": ["bao luu", "nam"],
    },
    {
        "category": "Co van hoc tap",
        "question": "Co van hoc tap co trach nhiem gi voi sinh vien?",
        "expect_keywords": ["co van", "sinh vien"],
    },
    {
        "category": "Ngoai pham vi",
        "question": "Gia ve may bay Ha Noi di Sai Gon hom nay la bao nhieu?",
        "expect_keywords": [],
        "expect_no_answer": True,
    },
]


def run_live_tests():
    try:
        validate_config()
    except Exception as e:
        print(f"[LOI CAU HINH] {e}")
        sys.exit(1)

    print("=" * 70)
    print(f"  LIVE TEST - HaUI RAG  |  Model: {ACTIVE_LLM_MODEL}")
    print("=" * 70)
    print()

    results = []
    total_time = 0.0

    for idx, tc in enumerate(TEST_CASES, 1):
        category = tc["category"]
        question = tc["question"]
        expect_keywords = tc.get("expect_keywords", [])
        expect_no_answer = tc.get("expect_no_answer", False)

        print(f"[{idx:02d}/{len(TEST_CASES)}] [{category}]")
        print(f"  Cau hoi : {question}")

        t0 = time.perf_counter()
        try:
            result = rag_query(question, top_k=DEFAULT_TOP_K)
            elapsed = time.perf_counter() - t0
            total_time += elapsed

            answer = result.get("answer", "")
            sources = result.get("sources", [])
            meta = result.get("meta", {})
            fallback = meta.get("fallback_used", False)
            chunks = meta.get("chunks_retrieved", 0)

            answer_preview = answer[:200].replace("\n", " ") if answer else "(Rong)"
            print(f"  Tra loi : {answer_preview}")
            print(f"  Thoi gian: {elapsed:.2f}s | Chunks: {chunks} | Fallback: {fallback}")

            if sources:
                citations = list({s.get("citation", "") for s in sources if s.get("citation")})
                print(f"  Nguon   : {' | '.join(citations[:3])}")

            passed = True
            notes = []

            if elapsed > 5.0:
                notes.append(f"CHAM ({elapsed:.1f}s > 5s)")
                passed = False

            if not expect_no_answer:
                if not answer or len(answer.strip()) < 20:
                    notes.append("Cau tra loi rong hoac qua ngan")
                    passed = False
                if not sources:
                    notes.append("Khong co nguon")

            status = "PASS" if passed else "FAIL"
            note_str = f" [{', '.join(notes)}]" if notes else ""
            print(f"  Ket qua : {status}{note_str}")
            results.append({"idx": idx, "category": category, "passed": passed, "elapsed": elapsed})

        except Exception as e:
            elapsed = time.perf_counter() - t0
            total_time += elapsed
            print(f"  [LOI] {type(e).__name__}: {e}")
            print(f"  Ket qua : FAIL [Exception]")
            results.append({"idx": idx, "category": category, "passed": False, "elapsed": elapsed})

        print()

    passed_count = sum(1 for r in results if r["passed"])
    failed_count = len(results) - passed_count
    avg_time = total_time / len(results) if results else 0

    print("=" * 70)
    print("  KET QUA TONG HOP")
    print("=" * 70)
    print(f"  PASS        : {passed_count}/{len(results)}")
    print(f"  FAIL        : {failed_count}/{len(results)}")
    print(f"  Trung binh  : {avg_time:.2f}s/query")
    print(f"  Tong thoi gian: {total_time:.1f}s")
    if failed_count > 0:
        print("  That bai:")
        for r in results:
            if not r["passed"]:
                print(f"    [{r['idx']:02d}] {r['category']} ({r['elapsed']:.2f}s)")
    print("=" * 70)


if __name__ == "__main__":
    run_live_tests()
