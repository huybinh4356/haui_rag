# Kế Hoạch Tái Cấu Trúc Giao Diện HAUI Regulation Assistant

## 1. Phân tích hiện trạng Frontend hiện tại (frontend/app.py)
- Cấu trúc đơn khối: Toàn bộ mã nguồn giao diện nằm trong 1 file monolithic (~307 dòng), trộn lẫn API calls, state, styling và render.
- Trải nghiệm chatbot chung chung: Bố cục đơn cột, phong cách demo sinh viên, thiếu chiều sâu của một hệ thống trợ lý học thuật.
- Lộ thông tin kỹ thuật: Hiển thị cổng kết nối (Port 8000), số lượng chunks DB, khoảng cách vector thô (distance: 0.1523), slider top_k ngay thanh sidebar.
- Trích dẫn dạng debug: Dùng expander và text area thô ráp để chứa dữ liệu chunk, không có tương tác trực tiếp giữa trích dẫn trong văn bản và tài liệu gốc.
- Thông báo hệ thống thô: Lộ thuật ngữ "Search Fallback activated" khi dùng tìm kiếm ngoài.

## 2. Nhận diện các vấn đề UX cốt lõi
1. Thiếu tính trang nghiêm và tin cậy của trợ lý văn bản quy chế đại học chính thống.
2. Thiếu bố cục 3 cột (Left Nav - Main Chat - Evidence Panel) hỗ trợ nghiên cứu và tra cứu đa chiều.
3. Thiếu khả năng tương tác hai chiều giữa số hiệu trích dẫn [1], [2] và thẻ bằng chứng tương ứng.
4. Trạng thái chờ chỉ là vòng quay vô định, không phản ánh các bước xử lý RAG.
5. Chưa phân tách được góc nhìn người dùng phổ thông và góc nhìn quản trị/chẩn đoán.

## 3. Kiến trúc thông tin mới (Information Architecture)
- Bố cục 3 cột tiêu chuẩn trên Desktop:
  + Cột Trái (Left Nav): Điều hướng, tạo cuộc trò chuyện mới, danh sách hội thoại phân nhóm (Hôm nay, Trước đó), Cài đặt và Giới thiệu.
  + Cột Giữa (Main Chat): Tiêu đề tối giản, trạng thái hệ thống tinh gọn, dòng tin nhắn Markdown chuẩn mực, Empty State trang trọng với gợi ý câu hỏi thông minh, thanh soạn thảo lớn đặt cố định.
  + Cột Phải (Evidence Panel): Danh mục các nguồn văn bản trích dẫn (Mã văn bản, Tên văn bản, Điều, Khoản, Nội dung trích dẫn). Khi bấm vào trích dẫn [1], panel chuyển ngay sang chế độ thẩm định nguồn chi tiết.
- Tùy chọn chuyển đổi giao diện:
  + Cho phép mở rộng / thu gọn Evidence Panel linh hoạt.
  + Chế độ Chẩn đoán & Cài đặt chuyên sâu (Diagnostics & Settings) mở riêng biệt.

## 4. Cấu trúc Module Component
```text
frontend/
├── app.py                     # Entry point & application controller
├── styles/
│   ├── __init__.py
│   └── theme.py               # Token màu sắc HaUI Navy, typography, bố cục CSS
├── state/
│   ├── __init__.py
│   └── session.py             # Quản lý đa hội thoại, lịch sử, trích dẫn được chọn
└── components/
    ├── __init__.py
    ├── topbar.py              # Thanh trạng thái tối giản
    ├── sidebar.py             # Thanh điều hướng và lịch sử hội thoại
    ├── empty_state.py         # Trạng thái rỗng với 4 câu hỏi gợi ý chuẩn
    ├── chat_view.py           # Dòng tin nhắn và huy hiệu trích dẫn tương tác
    ├── evidence_panel.py      # Bảng nguồn chứng cứ và kiến trúc Document Viewer
    ├── composer.py            # Thanh soạn thảo lớn và chỉ báo quy trình RAG
    ├── feedback.py            # Khối đánh giá chất lượng câu trả lời
    ├── settings_view.py       # Cài đặt người dùng & Chẩn đoán hệ thống (Dev)
    └── about_view.py          # Thông tin tra cứu quy chế HaUI
```

## 5. Tích hợp API và thay đổi Backend
1. Giữ nguyên tương thích với `POST /api/chat` và `GET /`.
2. Bổ sung endpoint `POST /api/feedback` để lưu nhận xét người dùng vào hệ thống log an toàn.
3. Hỗ trợ đầy đủ metadata trong schema `Source` (ma_van_ban, ten_van_ban, dieu, khoan, content, source_type).
