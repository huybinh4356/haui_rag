"""Component hiển thị Thông tin dự án và Danh mục văn bản quy chế HaUI đã số hóa."""

import streamlit as st


def render_about_view() -> None:
    """Hiển thị tổng quan giới thiệu sản phẩm và danh mục các văn bản quy chế chính thức."""
    col_head1, col_head2 = st.columns([8, 2])
    with col_head1:
        st.markdown("### Về Hệ Thống Tra Cứu Quy Chế HaUI")
        st.caption("Trợ lý trí tuệ nhân tạo chuyên sâu hỗ trợ tra cứu văn bản, quy chế và quy định.")
    with col_head2:
        if st.button("Quay lại hội thoại", type="primary", use_container_width=True):
            st.session_state.view_mode = "chat"
            st.rerun()

    st.markdown("---")

    st.markdown(
        """
        #### 1. Định vị sản phẩm
        **HAUI Regulation Assistant** là hệ thống trợ lý học thuật thông minh được phát triển nhằm phục vụ
        cán bộ, giảng viên, học viên và sinh viên Trường Đại học Công nghiệp Hà Nội trong việc tìm kiếm,
        đối chiếu và tra cứu chính xác các điều khoản trong hệ thống văn bản quy chế của Nhà trường.

        #### 2. Nguyên tắc vận hành cốt lõi
        - **Chính xác > Sáng tạo:** Trợ lý chỉ trả lời dựa trên cơ sở dữ liệu quy chế chính thức, tuyệt đối không bịa đặt.
        - **Bắt buộc trích dẫn nguồn:** Mọi câu trả lời đều có chỉ dẫn cụ thể đến Số quyết định, Điều và Khoản tương ứng.
        - **Minh bạch thông tin:** Người dùng luôn có thể đối chiếu trực tiếp giữa câu trả lời và nguyên văn đoạn trích.

        #### 3. Danh mục văn bản quy chế tiêu biểu đã nạp vào cơ sở dữ liệu
        """
    )

    documents_catalog = [
        {
            "code": "QĐ 41/QĐ-ĐHCN",
            "title": "Quy chế tuyển sinh và đào tạo trình độ thạc sĩ",
            "desc": "Quy định chi tiết về đối tượng, điều kiện dự tuyển, khối lượng học tập, luận văn và chuẩn đầu ra thạc sĩ.",
        },
        {
            "code": "QĐ 630/QĐ-ĐHCN",
            "title": "Quy chế đào tạo trình độ thạc sĩ",
            "desc": "Các quy định về điều kiện tốt nghiệp, bảo lưu kết quả, đánh giá học phần và khen thưởng kỷ luật.",
        },
        {
            "code": "QĐ Đào tạo Đại học",
            "title": "Quy chế đào tạo trình độ đại học hình thức chính quy",
            "desc": "Quy định tín chỉ, đăng ký học phần, điểm đánh giá, học bổng và quy trình công nhận tốt nghiệp đại học.",
        },
        {
            "code": "Quy định Học vụ",
            "title": "Chính sách học phí, miễn giảm học phí và bảo lưu",
            "desc": "Các hướng dẫn thủ tục hành chính học vụ dành cho sinh viên và học viên tại HaUI.",
        },
    ]

    for doc in documents_catalog:
        st.markdown(
            f"""
            <div class="source-card">
                <div class="source-code">{doc['code']}</div>
                <div class="source-heading">{doc['title']}</div>
                <div style="font-size: 0.83rem; color: #475569; margin-top: 4px;">{doc['desc']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.caption("Phiên bản hệ thống: haui_rag v1.1.0 • Bản quyền thuộc Đồ án chuyên ngành CNTT")
