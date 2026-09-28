---
name: streamlit-frontend-development
description: Hướng dẫn phát triển giao diện người dùng Streamlit cho haui_rag
---

# Hướng dẫn phát triển Streamlit Frontend (haui_rag)

## Quy định thiết kế bắt buộc
- **CẤM** sử dụng icon, emoji dưới mọi hình thức trong mã nguồn (tiêu đề, nút bấm, thông báo, markdown, logging, comment) trừ khi có yêu cầu rõ ràng từ người dùng.
- **CẤM** sử dụng chuỗi banner ký tự `==============================================================================` để note hoặc phân cách trong code. Sử dụng `#` để ghi chú.
- **CẤM** dùng các chuỗi ký tự ASCII (như `=`, `-`) để trang trí giao diện. Thiết kế giao diện phải căn chỉnh kích thước phù hợp với khung hình (responsive), sử dụng container, columns, divider và CSS chuẩn.

## UI/UX & Tương tác
- Hiển thị nguồn trích dẫn dạng expander (`st.expander`).
- Có nút đánh giá phản hồi (Hữu ích / Chưa đúng).
- Có danh sách câu hỏi gợi ý ở sidebar.
- Có nút xóa lịch sử trò chuyện.
- Hiển thị trạng thái đang xử lý bằng `st.spinner()`.
- Xử lý các exception: Timeout, ConnectionError.
- Hỗ trợ gọi Backend API và fallback trực tiếp nếu cần.
