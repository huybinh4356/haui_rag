"""Component hiển thị Cài đặt hệ thống, Thông số & Biểu đồ Đánh giá Thực nghiệm, và Chẩn đoán kỹ thuật."""

import json
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Callable
import streamlit as st
from psycopg2.extras import Json

from haui_rag.config import (
    ACTIVE_LLM_MODEL,
    BASE_DIR,
    DATA_DIR,
    DEFAULT_TOP_K,
    EMBEDDING_MODEL,
    ENABLE_QUERY_CACHE,
    LLM_PROVIDER,
    QUERY_CACHE_SIZE,
    USE_LLM_RERANK,
    USE_LOCAL_RERANK,
)
from haui_rag.core.rag_pipeline import clear_in_memory_cache, rag_query
from haui_rag.db.connection import connect_db
from haui_rag.db.conversation_queries import (
    clear_query_cache_db,
    get_system_evaluation_metrics,
    list_cached_queries,
)
from haui_rag.utils.helpers import enrich_chunk_metadata
from frontend.state.session import get_current_conversation


def _load_benchmark_report() -> dict[str, Any]:
    """Đọc dữ liệu báo cáo đánh giá benchmark từ data/test_data/evaluation_report.json nếu có."""
    report_path = DATA_DIR / "test_data" / "evaluation_report.json"
    if not report_path.exists():
        return {}
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_test_questions() -> list[dict[str, Any]]:
    """Đọc danh sách 30 câu hỏi kiểm thử từ data/test_data/test_questions.json."""
    q_path = DATA_DIR / "test_data" / "test_questions.json"
    if not q_path.exists():
        return []
    try:
        with open(q_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _render_evaluation_tab() -> None:
    """Hiển thị thuần túy các thông số đo đạc thực tế và biểu đồ phân tích từ PostgreSQL + Benchmark."""
    live = get_system_evaluation_metrics()
    bench_report = _load_benchmark_report()
    bench_details = bench_report.get("details", []) if isinstance(bench_report, dict) else []

    # 1. Hàng thông số thực tế từ PostgreSQL (Không tự gán điểm)
    st.markdown("##### 1. Thông số Vận hành Thực tế từ Cơ sở dữ liệu (PostgreSQL Live Telemetry)")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric(
            "Kho dữ liệu Vector (Chunks)",
            f"{live.get('total_documents', 0):,}",
            delta=f"{live.get('total_files', 0)} văn bản PDF",
        )
    with m2:
        st.metric(
            "Số lượt trả lời / Hội thoại",
            f"{live.get('total_assistant_answers', 0)} câu",
            delta=f"{live.get('total_conversations', 0)} phiên chat",
        )
    with m3:
        audited = live.get("audited_count", 0)
        gnd_cnt = live.get("grounded_count", 0)
        gnd_pct = live.get("grounded_rate_percent", 0.0)
        st.metric(
            "Tỷ lệ trích dẫn khớp nguồn (Grounded)",
            f"{gnd_pct:.1f}%" if audited > 0 else "Chưa có mẫu",
            delta=f"{gnd_cnt}/{audited} câu đã kiểm chứng",
        )
    with m4:
        avg_ms = live.get("avg_latency_ms", 0)
        p95_ms = live.get("p95_latency_ms", 0)
        st.metric(
            "Độ trễ phản hồi TB (Latency)",
            f"{avg_ms:,} ms",
            delta=f"P95: {p95_ms:,} ms",
        )

    m5, m6, m7, m8 = st.columns(4)
    with m5:
        st.metric(
            "Điểm xác thực trích dẫn TB",
            f"{live.get('avg_verification_score', 0.0):.1f}%",
            delta="Tỷ lệ citation có trong ngữ cảnh",
        )
    with m6:
        st.metric(
            "Số chunks ngữ cảnh TB / câu",
            f"{live.get('avg_sources_per_answer', 0.0):.1f} chunks",
            delta=f"Top-K hạt giống = {st.session_state.get('top_k', DEFAULT_TOP_K)}",
        )
    with m7:
        fb_cnt = live.get("fallback_count", 0)
        fb_pct = live.get("fallback_rate_percent", 0.0)
        st.metric(
            "Tỷ lệ gọi Search Fallback",
            f"{fb_pct:.1f}%",
            delta=f"{fb_cnt} lượt tra cứu web HaUI",
        )
    with m8:
        fb_total = live.get("feedback_total", 0)
        fb_help = live.get("feedback_helpful", 0)
        fb_unhelp = live.get("feedback_unhelpful", 0)
        st.metric(
            "Phản hồi người dùng (Feedback)",
            f"{fb_help} tốt / {fb_unhelp} lỗi",
            delta=f"Tổng: {fb_total} lượt đánh giá",
        )

    st.markdown("---")

    # 2. Hệ thống Biểu đồ Trực quan (Charts)
    st.markdown("##### 2. Biểu đồ Phân tích Dữ liệu & Hiệu năng Thực tế")

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.markdown("**Biểu đồ 1: Độ trễ phản hồi (ms) qua các lượt truy vấn gần nhất**")
        recent_lats = live.get("recent_latencies", [])
        if recent_lats:
            chart_lat_data = {
                item["Lượt"]: item["Độ trễ (ms)"]
                for item in recent_lats
            }
            st.line_chart(chart_lat_data, height=260)
        else:
            st.caption("Chưa có dữ liệu độ trễ trong bảng messages.")

    with col_chart2:
        st.markdown("**Biểu đồ 2: Số lượng Chunks ngữ cảnh truy xuất ở mỗi câu trả lời**")
        if recent_lats:
            chart_src_data = {
                item["Lượt"]: item["Số chunks"]
                for item in recent_lats
            }
            st.bar_chart(chart_src_data, height=260)
        else:
            st.caption("Chưa có dữ liệu số lượng nguồn trích dẫn.")

    col_chart3, col_chart4 = st.columns(2)
    with col_chart3:
        st.markdown("**Biểu đồ 3: Phân bố số lượng Chunks theo Văn bản quy chế trong DB**")
        docs_by_file = live.get("docs_by_file", [])
        if docs_by_file:
            normalized_doc_counts: dict[str, int] = {}
            for row in docs_by_file:
                raw_name = str(row.get("Văn bản", ""))
                enriched = enrich_chunk_metadata({"ten_file": raw_name})
                code_label = str(enriched.get("ma_van_ban") or raw_name)[:22]
                normalized_doc_counts[code_label] = normalized_doc_counts.get(code_label, 0) + int(row.get("Số chunks", 0))
            st.bar_chart(normalized_doc_counts, height=260)
        else:
            st.caption("Không đọc được phân bố bảng documents.")

    with col_chart4:
        st.markdown("**Biểu đồ 4: Phân bố loại câu hỏi & Kết quả kiểm chứng trích dẫn**")
        q_map = live.get("query_type_breakdown", {}) or {}
        breakdown_chart = {
            "Factual (Sự kiện)": int(q_map.get("factual", 0)),
            "Procedural (Quy trình)": int(q_map.get("procedural", 0)),
            "Comparative (So sánh)": int(q_map.get("comparative", 0)),
            "Out-of-scope": int(q_map.get("out_of_scope", 0)),
            "Grounded (Khớp nguồn)": int(live.get("grounded_count", 0)),
            "Ungrounded (Lệch nguồn)": int(live.get("ungrounded_count", 0)),
        }
        st.bar_chart(breakdown_chart, height=260)

    # 3. Biểu đồ & Bảng thống kê từ tập 30 câu hỏi Benchmark (nếu có)
    if bench_details:
        st.markdown("---")
        st.markdown("##### 3. Thống kê Thực nghiệm trên Bộ 30 Câu hỏi Benchmark (`evaluation_report.json`)")
        total_b = len(bench_details)
        answered_b = sum(
            1
            for d in bench_details
            if "không tìm thấy" not in str(d.get("answer", "")).lower()
            and d.get("type") != "out_of_scope"
        )
        rejected_in_scope = sum(
            1
            for d in bench_details
            if "không tìm thấy" in str(d.get("answer", "")).lower()
            and d.get("type") in ("factual", "procedural")
        )
        safe_oos = sum(
            1
            for d in bench_details
            if d.get("type") == "out_of_scope" and d.get("is_safe_rejection")
        )
        b_lats = [float(d.get("elapsed_seconds", 0.0)) for d in bench_details if d.get("elapsed_seconds")]
        avg_b_lat = round(sum(b_lats) / len(b_lats), 2) if b_lats else 0.0

        b1, b2, b3, b4 = st.columns(4)
        with b1:
            st.metric("Tổng số câu hỏi Benchmark", f"{total_b} câu")
        with b2:
            st.metric("Trả lời có trích dẫn (In-scope)", f"{answered_b}/25 câu")
        with b3:
            st.metric("Chưa tìm thấy thông tin (In-scope)", f"{rejected_in_scope}/25 câu")
        with b4:
            st.metric("Chặn đúng câu ngoài phạm vi", f"{safe_oos}/5 câu", delta=f"TB: {avg_b_lat}s/câu")

        bench_lat_chart = {
            f"Q{int(d.get('id', i)):02d}": float(d.get("elapsed_seconds", 0.0))
            for i, d in enumerate(bench_details, start=1)
        }
        st.markdown("**Biểu đồ 5: Thời gian phản hồi (giây) của từng câu trong bộ 30 câu hỏi Benchmark**")
        st.bar_chart(bench_lat_chart, height=230)

        with st.expander(f"Xem bảng dữ liệu thô của {total_b} câu hỏi Benchmark", expanded=False):
            table_rows = []
            for item in bench_details:
                ans_text = str(item.get("answer", ""))
                is_not_found = "không tìm thấy" in ans_text.lower()
                table_rows.append(
                    {
                        "ID": item.get("id"),
                        "Loại": item.get("type", ""),
                        "Câu hỏi": item.get("question", ""),
                        "Số chunks": item.get("sources_count", 0),
                        "Trạng thái trả lời": (
                            "Từ chối OOS đúng"
                            if item.get("type") == "out_of_scope" and item.get("is_safe_rejection")
                            else ("Không tìm thấy trong ngữ cảnh" if is_not_found else "Đã trả lời kèm trích dẫn")
                        ),
                        "Thời gian (s)": item.get("elapsed_seconds", 0.0),
                    }
                )
            st.dataframe(table_rows, use_container_width=True, hide_index=True)

    st.markdown("---")

    # 4. Công cụ chạy đo thông số trực tiếp trên tập câu hỏi mẫu
    st.markdown("##### 4. Chạy Đo thông số Trực tiếp trên Tập câu hỏi Kiểm thử (Live Benchmark Runner)")
    col_run1, col_run2 = st.columns([6, 4])
    with col_run1:
        sample_count = st.slider(
            "Số lượng câu hỏi muốn chạy đo trực tiếp:",
            min_value=1,
            max_value=10,
            value=3,
            step=1,
            key="eval_quick_sample_slider",
        )
    with col_run2:
        st.write("")
        run_quick_btn = st.button(
            "Chạy đo thực nghiệm",
            type="primary",
            use_container_width=True,
            key="btn_run_quick_eval",
        )

    if run_quick_btn:
        questions = _load_test_questions()[:sample_count]
        if not questions:
            st.warning("Không tìm thấy file data/test_data/test_questions.json.")
        else:
            progress = st.progress(0, text="Đang chạy đo thực nghiệm...")
            quick_results: list[dict[str, Any]] = []
            for idx, q_item in enumerate(questions, start=1):
                q_text = q_item.get("question", "")
                q_type = q_item.get("type", "factual")
                exp_sources = q_item.get("expected_sources", [])
                exp_keywords = q_item.get("expected_keywords", [])
                progress.progress(
                    int((idx - 1) / len(questions) * 100),
                    text=f"Đang chạy câu {idx}/{len(questions)}: {q_text}",
                )
                t0 = time.perf_counter()
                res = rag_query(q_text, top_k=st.session_state.get("top_k", DEFAULT_TOP_K))
                dt_ms = int((time.perf_counter() - t0) * 1000)

                ans = str(res.get("answer", ""))
                srcs = res.get("sources", []) or []
                audit = res.get("citation_audit") or {}
                ans_low = ans.lower()

                matched_src = any(
                    any(es.lower() in str(s.get("citation", "")).lower() for es in exp_sources)
                    or any(es.lower() in str(s.get("ma_van_ban", "")).lower() for es in exp_sources)
                    or any(es.lower() in ans_low for es in exp_sources)
                    for s in srcs
                ) if exp_sources else True
                matched_kw = sum(1 for kw in exp_keywords if kw.lower() in ans_low)
                kw_ratio = f"{matched_kw}/{len(exp_keywords)}" if exp_keywords else "N/A"

                quick_results.append(
                    {
                        "ID": q_item.get("id", idx),
                        "Loại": q_type,
                        "Câu hỏi": q_text,
                        "Số chunks": len(srcs),
                        "Khớp mã VB kỳ vọng": "Có" if matched_src else "Không",
                        "Từ khóa khớp": kw_ratio,
                        "Tỷ lệ trích dẫn hợp lệ": f"{float(audit.get('verification_score', 1.0)) * 100:.0f}%",
                        "Độ trễ (ms)": dt_ms,
                    }
                )
            progress.progress(100, text="Đã hoàn tất chạy đo thực nghiệm.")
            st.session_state["last_quick_eval_results"] = quick_results

    if st.session_state.get("last_quick_eval_results"):
        st.dataframe(st.session_state["last_quick_eval_results"], use_container_width=True, hide_index=True)


def _ingest_uploaded_pdf(
    uploaded_file: Any,
    override_meta: dict[str, str],
    replace_existing: bool,
    sleep_seconds: float,
    on_progress: Callable[[float, str], None],
) -> dict[str, Any]:
    """
    Thực thi quy trình nạp file PDF trực tiếp từ giao diện Streamlit:
    1. Lưu file PDF vào data/raw_pdf/.
    2. Gọi nguyên bản process_single_file() từ scripts/chunking.py (OCR + Clean + Chunking theo Điều/Khoản).
    3. Áp dụng thông tin Metadata người dùng nhập (nếu có) và lưu JSON vào data/output_json/.
    4. Gọi nguyên bản get_embedding() từ scripts/embedding.py để sinh vector 3072 chiều và INSERT vào PostgreSQL.
    5. Lưu trữ PDF đã xử lý sang data/data_processed/ và làm mới Cache câu hỏi.
    """
    scripts_dir = str(BASE_DIR / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    import chunking as legacy_chunking
    import embedding as legacy_embedding

    filename = uploaded_file.name
    raw_pdf_dir = Path(legacy_chunking.INPUT_DIR)
    output_json_dir = Path(legacy_chunking.OUTPUT_DIR)
    processed_dir = Path(legacy_chunking.PROCESSED_DIR)

    raw_pdf_dir.mkdir(parents=True, exist_ok=True)
    output_json_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = raw_pdf_dir / filename
    on_progress(0.05, f"Đang lưu file '{filename}' vào thư mục {raw_pdf_dir}...")
    with open(pdf_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Bước 1: Chạy Chunking & OCR nguyên bản từ scripts/chunking.py
    on_progress(0.15, f"Đang đọc văn bản / OCR và tách Điều, Khoản cho '{filename}'...")
    chunks = legacy_chunking.process_single_file(str(pdf_path))
    if not chunks:
        raise RuntimeError(f"Không thể trích xuất văn bản hoặc tách chunk từ file '{filename}'.")

    # Bước 2: Bổ sung metadata tùy chỉnh nếu người dùng nhập trên UI
    for ch in chunks:
        meta = ch.get("metadata") or {}
        if override_meta.get("ma_van_ban"):
            meta["ma_van_ban"] = override_meta["ma_van_ban"].strip()
        if override_meta.get("ten_van_ban"):
            meta["ten_van_ban"] = override_meta["ten_van_ban"].strip()
        if override_meta.get("loai_van_ban"):
            meta["loai_van_ban"] = override_meta["loai_van_ban"].strip()
        if override_meta.get("bac_dao_tao"):
            meta["bac_dao_tao"] = override_meta["bac_dao_tao"].strip()
        ch["metadata"] = meta

    # Lưu file JSON riêng và cập nhật all_chunks.json giống hệt scripts/chunking.py
    json_out_path = output_json_dir / f"{pdf_path.stem}.json"
    with open(json_out_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    all_chunks_combined: list[dict[str, Any]] = []
    for jf in sorted(output_json_dir.glob("*.json")):
        if jf.name == "all_chunks.json":
            continue
        try:
            with open(jf, "r", encoding="utf-8") as f:
                fc = json.load(f)
                if isinstance(fc, list):
                    all_chunks_combined.extend(fc)
        except Exception:
            pass
    with open(output_json_dir / "all_chunks.json", "w", encoding="utf-8") as f:
        json.dump(all_chunks_combined, f, ensure_ascii=False, indent=2)

    # Bước 3: Tạo Embedding (3072 chiều) bằng scripts/embedding.py và nạp vào PostgreSQL
    conn = connect_db()
    inserted_count = 0
    failed_count = 0
    deleted_old = 0

    try:
        with conn.cursor() as cur:
            if replace_existing:
                cur.execute(
                    "DELETE FROM documents WHERE metadata->>'ten_file' = %s;",
                    (filename,),
                )
                deleted_old = cur.rowcount or 0
                conn.commit()

            total_chunks = len(chunks)
            for idx, chunk in enumerate(chunks, start=1):
                pct = 0.25 + 0.70 * (idx / max(1, total_chunks))
                dieu_lbl = (chunk.get("metadata") or {}).get("dieu", "?")
                khoan_lbl = (chunk.get("metadata") or {}).get("khoan", "?")
                on_progress(
                    pct,
                    f"Đang tạo Embedding & nạp DB chunk {idx}/{total_chunks} (Điều {dieu_lbl}, Khoản {khoan_lbl})...",
                )

                content = chunk["content"]
                metadata = dict(chunk.get("metadata") or {})
                metadata["chunk_index"] = idx - 1

                emb_vec = legacy_embedding.get_embedding(content, task_type="RETRIEVAL_DOCUMENT")
                if emb_vec is None:
                    failed_count += 1
                    continue

                clean_meta: dict[str, Any] = {}
                for k, v in metadata.items():
                    if v is None:
                        clean_meta[k] = ""
                    elif isinstance(v, (str, int, float, bool)):
                        clean_meta[k] = v
                    else:
                        clean_meta[k] = str(v)

                cur.execute(
                    "INSERT INTO documents (content, metadata, embedding) VALUES (%s, %s, %s);",
                    (content, Json(clean_meta), emb_vec),
                )
                inserted_count += 1
                if inserted_count % 10 == 0:
                    conn.commit()

                if idx < total_chunks and sleep_seconds > 0:
                    time.sleep(sleep_seconds)

            conn.commit()
    finally:
        if conn and not conn.closed:
            conn.close()

    # Bước 4: Di chuyển file PDF sang data_processed/ và làm mới cache
    processed_target = processed_dir / filename
    if processed_target.exists():
        processed_target.unlink()
    if pdf_path.exists():
        shutil.move(str(pdf_path), str(processed_target))

    clear_in_memory_cache()
    clear_query_cache_db()
    on_progress(1.0, f"Hoàn tất nạp '{filename}': {inserted_count}/{len(chunks)} chunks vào PostgreSQL!")

    return {
        "filename": filename,
        "total_chunks": len(chunks),
        "inserted_chunks": inserted_count,
        "failed_chunks": failed_count,
        "deleted_old_chunks": deleted_old,
        "json_path": str(json_out_path),
        "sample_chunks": chunks[:5],
    }


def _render_ingestion_tab() -> None:
    """Hiển thị Cổng Nạp Văn bản Quy chế PDF trực tiếp trên giao diện Streamlit."""
    st.markdown("#### Cổng Nạp Văn bản Quy chế Mới vào Hệ thống (Direct PDF Ingestion)")
    st.caption(
        "Tải lên file PDF quy chế mới (có cấu trúc Điều/Khoản như các văn bản hiện hành). "
        "Hệ thống sẽ chạy trực tiếp bộ xử lý OCR + Chunking (`scripts/chunking.py`) và tạo Vector Embedding 3072 chiều "
        "(`scripts/embedding.py`) nạp thẳng vào PostgreSQL mà không cần chạy lệnh thủ công."
    )

    uploaded_pdf = st.file_uploader(
        "Chọn file PDF văn bản quy chế HaUI cần nạp:",
        type=["pdf"],
        accept_multiple_files=False,
        key="pdf_ingestion_uploader",
    )

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        inp_ma_vb = st.text_input(
            "Mã văn bản (để trống nếu muốn tự động nhận diện từ PDF):",
            placeholder="Ví dụ: 888/QĐ-ĐHCN",
            key="ingest_ma_vb",
        )
        inp_loai_vb = st.selectbox(
            "Loại văn bản:",
            options=["Tự động nhận diện", "Quyết định", "Quy chế", "Quy định", "Thông tư", "Thông báo", "Hướng dẫn"],
            index=0,
            key="ingest_loai_vb",
        )
    with col_m2:
        inp_ten_vb = st.text_input(
            "Tên văn bản quy chế (tùy chọn):",
            placeholder="Ví dụ: Quy định về đào tạo trình độ đại học...",
            key="ingest_ten_vb",
        )
        inp_bac_dt = st.selectbox(
            "Bậc đào tạo áp dụng:",
            options=["Tự động / Chung", "đại học", "thạc sĩ", "tiến sĩ", "chung"],
            index=0,
            key="ingest_bac_dt",
        )

    col_opt1, col_opt2, col_opt3 = st.columns([4, 3, 3])
    with col_opt1:
        replace_old = st.checkbox(
            "Ghi đè (xóa chunks cũ nếu trùng tên file PDF đã nạp trước đó)",
            value=True,
            key="ingest_replace_old",
        )
    with col_opt2:
        sleep_sec = st.number_input(
            "Thời gian nghỉ giữa 2 chunks (giây):",
            min_value=0.0,
            max_value=5.0,
            value=1.0,
            step=0.5,
            help="Giúp tránh chạm giới hạn Rate Limit 429 của Gemini Embedding API.",
            key="ingest_sleep_sec",
        )
    with col_opt3:
        st.write("")
        start_ingest_btn = st.button(
            "Bắt đầu Xử lý & Nạp vào DB",
            type="primary",
            use_container_width=True,
            disabled=(uploaded_pdf is None),
            key="btn_start_pdf_ingest",
        )

    if start_ingest_btn and uploaded_pdf is not None:
        progress_bar = st.progress(0, text="Đang chuẩn bị xử lý file PDF...")
        status_box = st.empty()

        def _update_ui(pct: float, msg: str) -> None:
            progress_bar.progress(min(100, max(0, int(pct * 100))), text=msg)
            status_box.info(msg)

        override_meta = {
            "ma_van_ban": inp_ma_vb.strip(),
            "ten_van_ban": inp_ten_vb.strip(),
            "loai_van_ban": "" if inp_loai_vb == "Tự động nhận diện" else inp_loai_vb,
            "bac_dao_tao": "" if inp_bac_dt.startswith("Tự động") else inp_bac_dt,
        }

        try:
            result = _ingest_uploaded_pdf(
                uploaded_file=uploaded_pdf,
                override_meta=override_meta,
                replace_existing=replace_old,
                sleep_seconds=float(sleep_sec),
                on_progress=_update_ui,
            )
            status_box.empty()
            st.success(
                f"Đã nạp thành công văn bản **{result['filename']}**: "
                f"**{result['inserted_chunks']}/{result['total_chunks']} chunks** đã được lưu vào bảng `documents` "
                f"(Đã xóa {result['deleted_old_chunks']} chunks cũ trùng tên file)."
            )
            st.session_state["last_ingest_result"] = result
        except Exception as e:
            status_box.empty()
            st.error(f"Lỗi trong quá trình nạp file PDF: {e}")

    if st.session_state.get("last_ingest_result"):
        last_res = st.session_state["last_ingest_result"]
        with st.expander(f"Xem trước 5 Chunks đầu tiên vừa tách từ '{last_res.get('filename')}'", expanded=True):
            for idx, ch in enumerate(last_res.get("sample_chunks", []), start=1):
                m = ch.get("metadata") or {}
                st.markdown(
                    f"**Chunk #{idx}** — Mã VB: `{m.get('ma_van_ban') or 'Tự động'}` | "
                    f"Điều `{m.get('dieu', '?')}` | Khoản `{m.get('khoan', '?')}`"
                )
                st.code(ch.get("content", ""), language="text")

    st.markdown("---")
    st.markdown("##### Danh sách các Văn bản Quy chế Hiện có trong PostgreSQL")
    live = get_system_evaluation_metrics()
    docs_list = live.get("docs_by_file", [])
    if docs_list:
        enriched_rows = []
        for row in docs_list:
            raw_file = str(row.get("Văn bản", ""))
            enr = enrich_chunk_metadata({"ten_file": raw_file})
            enriched_rows.append(
                {
                    "Tên file / Nguồn": raw_file,
                    "Mã văn bản": enr.get("ma_van_ban") or "Chưa gán",
                    "Tên văn bản quy chế": enr.get("ten_van_ban") or raw_file,
                    "Bậc đào tạo": enr.get("bac_dao_tao") or "chung",
                    "Số lượng Chunks": int(row.get("Số chunks", 0)),
                }
            )
        st.dataframe(enriched_rows, use_container_width=True, hide_index=True)
    else:
        st.caption("Chưa có văn bản nào trong bảng documents.")


def render_settings_view(health_data: dict[str, Any]) -> None:
    """
    Hiển thị giao diện cấu hình phân cấp: Thông số & Biểu đồ đánh giá, Nạp dữ liệu PDF, Cài đặt và Chẩn đoán kỹ thuật.

    Args:
        health_data: Dữ liệu kết nối từ Backend API.
    """
    col_head1, col_head2 = st.columns([8, 2])
    with col_head1:
        st.markdown("### Cài đặt hệ thống, Nạp Văn bản & Thống kê Đánh giá")
        st.caption("Tải lên văn bản quy chế PDF mới, theo dõi thông số thực nghiệm, biểu đồ hiệu năng và cấu hình hệ thống.")
    with col_head2:
        if st.button("Quay lại hội thoại", type="primary", use_container_width=True):
            st.session_state.view_mode = "chat"
            st.rerun()

    st.markdown("---")

    # Phân cấp đối tượng: Simple Mode vs Advanced Developer Mode
    user_mode = st.radio(
        "Chế độ hiển thị:",
        options=["Người dùng cơ bản", "Chuyên sâu / Nhà phát triển (Developer)"],
        horizontal=True,
        index=0 if st.session_state.user_mode == "simple" else 1,
    )
    st.session_state.user_mode = "simple" if user_mode.startswith("Người dùng") else "advanced"

    if st.session_state.user_mode == "simple":
        st.caption(
            "Chuyển sang chế độ 'Chuyên sâu / Nhà phát triển (Developer)' để mở cổng Nạp Văn bản Quy chế (PDF), "
            "Thông số & Biểu đồ Đánh giá, Quản lý Query Cache và Chẩn đoán kỹ thuật."
        )
        tab_general, tab_ai, tab_retrieval = st.tabs([
            "Cài đặt chung",
            "Mô hình AI",
            "Thuật toán truy xuất",
        ])
        tab_ingest = None
        tab_eval = None
        tab_diag = None
    else:
        tab_ingest, tab_eval, tab_general, tab_ai, tab_retrieval, tab_diag = st.tabs([
            "Nạp Văn bản Quy chế (PDF)",
            "Thông số & Biểu đồ Đánh giá",
            "Cài đặt chung",
            "Mô hình AI",
            "Thuật toán truy xuất",
            "Chẩn đoán kỹ thuật (Diagnostics)",
        ])

    if tab_ingest is not None:
        with tab_ingest:
            _render_ingestion_tab()

    if tab_eval is not None:
        with tab_eval:
            _render_evaluation_tab()

    with tab_general:
        st.markdown("#### Tùy chọn giao diện & ngôn ngữ")
        st.selectbox("Ngôn ngữ giao diện:", ["Tiếng Việt (Mặc định)", "English"], index=0)
        curr_mode = st.session_state.get("chat_layout_mode", "bottom")
        selected_lo = st.selectbox(
            "Vị trí thanh nhập câu hỏi:",
            options=["Dưới đáy màn hình (Chuẩn AI - Lịch sử đẩy lên trên)", "Trên cùng (Thanh chat ở trên, lịch sử ở dưới)"],
            index=0 if curr_mode == "bottom" else 1,
        )
        st.session_state.chat_layout_mode = "bottom" if selected_lo.startswith("Dưới đáy") else "top"
        st.selectbox("Bố cục Evidence Panel:", ["Luôn mở bên phải", "Thu gọn khi cần"], index=0)
        st.caption("Hệ thống được tối ưu hóa cho tài liệu học thuật tiếng Việt của Nhà trường.")

    with tab_ai:
        st.markdown("#### Cấu hình Mô hình Ngôn ngữ (LLM)")
        st.markdown(f"- **Nhà cung cấp hiện tại:** `{LLM_PROVIDER.upper()}`")
        st.markdown(f"- **Mô hình hoạt động:** `{ACTIVE_LLM_MODEL}`")
        st.markdown(f"- **Mô hình Embedding:** `{EMBEDDING_MODEL}` (3072 chiều)")
        st.info("Để chuyển đổi giữa Local LLM (Qwen) và Gemini Cloud, cấu hình tại file môi trường .env hoặc sử dụng run.bat.")

    with tab_retrieval:
        st.markdown("#### Tham số tìm kiếm tài liệu (Retrieval)")
        top_k_select = st.slider(
            "Số lượng đoạn văn bản trích dẫn tối đa (Top K):",
            min_value=1,
            max_value=10,
            value=st.session_state.top_k,
            step=1,
            help="Số lượng chunks hạt giống được lấy ra từ cơ sở dữ liệu trước khi mở rộng theo Điều.",
        )
        st.session_state.top_k = top_k_select

        st.checkbox("Kích hoạt LLM Reranking ngữ nghĩa (Gemini)", value=USE_LLM_RERANK, disabled=True)
        st.checkbox("Kích hoạt Local Reranking (Ollama)", value=USE_LOCAL_RERANK, disabled=True)
        st.caption(
            "Pipeline V2 áp dụng Reciprocal Rank Fusion (RRF) kết hợp Vector Search, Weighted Keyword Search, "
            "Subject-Aware Boost và mở rộng ngữ cảnh đa Điều."
        )

        if st.session_state.user_mode == "advanced":
            st.markdown("---")
            st.markdown("#### Bộ nhớ đệm Câu hỏi 2 tầng (L1 RAM + L2 PostgreSQL Query Cache)")
            st.markdown(
                f"- **Trạng thái Cache:** `{'Đang bật' if ENABLE_QUERY_CACHE else 'Đang tắt'}` "
                f"(Dung lượng L1 RAM: `{QUERY_CACHE_SIZE}` câu hỏi + L2 lưu bền vững trong bảng `query_cache`)"
            )
            cached_items = list_cached_queries(limit=50)
            total_hits = sum(int(item.get("hit_count", 0)) for item in cached_items)
            col_c1, col_c2, col_c3 = st.columns([3, 3, 4])
            with col_c1:
                st.metric("Số câu hỏi đã lưu trong Cache", f"{len(cached_items)} câu")
            with col_c2:
                st.metric("Số lần tái sử dụng (Cache Hits)", f"{total_hits} lượt")
            with col_c3:
                st.write("")
                if st.button("Xóa toàn bộ Cache câu hỏi", use_container_width=True, key="btn_clear_query_cache"):
                    clear_in_memory_cache()
                    deleted_cnt = clear_query_cache_db()
                    st.success(f"Đã xóa {deleted_cnt} bản ghi trong bảng query_cache và làm mới RAM cache.")
                    st.rerun()

            if cached_items:
                table_cache = [
                    {
                        "Câu hỏi gốc": item.get("original_query"),
                        "Chuẩn hóa": item.get("normalized_query"),
                        "Top K": item.get("top_k"),
                        "Số nguồn": item.get("sources_count"),
                        "Số lần hỏi lại (Hits)": item.get("hit_count"),
                        "Lần truy cập cuối": str(item.get("last_hit_at", ""))[:19],
                    }
                    for item in cached_items
                ]
                st.dataframe(table_cache, use_container_width=True, hide_index=True)
            else:
                st.caption("Chưa có câu hỏi nào được lưu trong bảng query_cache.")

    if tab_diag is not None:
        with tab_diag:
            st.markdown("#### Bảng chẩn đoán kỹ thuật (Developer Diagnostics)")
            # 1. Thông số Backend & Database
            st.markdown("##### 1. Trạng thái hạ tầng")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Cơ sở dữ liệu", health_data.get("database", "connected"))
            with c2:
                st.metric("Số lượng chunks đã nạp", health_data.get("total_documents", "1714+"))
            with c3:
                st.metric("Cổng Backend API", "Port 8000")

            # 2. Thông số truy vấn gần nhất
            st.markdown("##### 2. Chi tiết truy vấn gần nhất")
            current_conv = get_current_conversation()
            assistant_msgs = [m for m in current_conv.get("messages", []) if m.get("role") == "assistant"]

            if assistant_msgs:
                last_msg = assistant_msgs[-1]
                audit = last_msg.get("citation_audit") or {}

                st.markdown(
                    f"""
                    <div class="diag-card">
                        <div class="diag-row">
                            <span class="diag-key">Phân loại câu hỏi (Query Type):</span>
                            <span class="diag-val">{last_msg.get('query_type') or 'N/A'}</span>
                        </div>
                        <div class="diag-row">
                            <span class="diag-key">Tổng thời gian phản hồi:</span>
                            <span class="diag-val">{last_msg.get('response_time_ms', 0)} ms</span>
                        </div>
                        <div class="diag-row">
                            <span class="diag-key">Số lượng nguồn trích dẫn:</span>
                            <span class="diag-val">{len(last_msg.get('sources', []))} văn bản</span>
                        </div>
                        <div class="diag-row">
                            <span class="diag-key">Sử dụng Search Fallback:</span>
                            <span class="diag-val">{'Có' if last_msg.get('fallback_used') else 'Không (Thuần cơ sở dữ liệu)'}</span>
                        </div>
                        <div class="diag-row">
                            <span class="diag-key">Thẩm định trích dẫn (Grounded):</span>
                            <span class="diag-val">{'Đạt tiêu chuẩn 100%' if audit.get('is_grounded', True) else 'Cần xem xét'}</span>
                        </div>
                        <div class="diag-row">
                            <span class="diag-key">Điểm xác thực (Verification Score):</span>
                            <span class="diag-val">{audit.get('verification_score', 1.0)}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Cho phép nhà phát triển kiểm tra metadata chi tiết của từng chunk
                with st.expander("Kiểm tra chi tiết Metadata từng Chunk", expanded=False):
                    for idx, s in enumerate(last_msg.get("sources", [])):
                        st.markdown(f"**Chunk #{s.get('chunk_id')}** - {s.get('citation')}")
                        st.json(s)
            else:
                st.caption("Chưa có truy vấn nào được thực hiện trong phiên hiện tại.")
