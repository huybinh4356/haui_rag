"""Component hiển thị Cài đặt hệ thống và Bảng chẩn đoán kỹ thuật (Developer Diagnostics)."""

from typing import Any
import streamlit as st

from haui_rag.config import (
    ACTIVE_LLM_MODEL,
    DEFAULT_TOP_K,
    EMBEDDING_MODEL,
    LLM_PROVIDER,
    USE_LLM_RERANK,
)
from frontend.state.session import get_current_conversation


def render_settings_view(health_data: dict[str, Any]) -> None:
    """
    Hiển thị giao diện cấu hình phân cấp: Chế độ cơ bản và Chế độ nâng cao/Chẩn đoán kỹ thuật.

    Args:
        health_data: Dữ liệu kết nối từ Backend API.
    """
    col_head1, col_head2 = st.columns([8, 2])
    with col_head1:
        st.markdown("### Cài đặt hệ thống & Chẩn đoán")
        st.caption("Tùy biến tham số tra cứu quy chế và kiểm tra tình trạng vận hành hệ thống.")
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

    tab_general, tab_ai, tab_retrieval, tab_diag = st.tabs([
        "Cài đặt chung",
        "Mô hình AI",
        "Thuật toán truy xuất",
        "Chẩn đoán kỹ thuật (Diagnostics)",
    ])

    with tab_general:
        st.markdown("#### Tùy chọn giao diện & ngôn ngữ")
        st.selectbox("Ngôn ngữ giao diện:", ["Tiếng Việt (Mặc định)", "English"], index=0)
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
            help="Số lượng chunks được lấy ra từ cơ sở dữ liệu để đưa vào ngữ cảnh sinh câu trả lời.",
        )
        st.session_state.top_k = top_k_select

        st.checkbox("Kích hoạt LLM Reranking ngữ nghĩa", value=USE_LLM_RERANK, disabled=True)
        st.caption("Mặc định áp dụng Reciprocal Rank Fusion (RRF) kết hợp Vector Search và Full-text Search.")

    with tab_diag:
        st.markdown("#### Bảng chẩn đoán kỹ thuật (Developer Diagnostics)")
        if st.session_state.user_mode == "simple":
            st.info("Chuyển sang chế độ 'Chuyên sâu / Nhà phát triển' ở trên để kiểm tra toàn bộ thông số chi tiết.")
        else:
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
