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

## Khi nào dùng skill này

- Xây dựng giao diện chat
- Hiển thị câu trả lời + trích dẫn
- Quản lý lịch sử chat
- Kết nối với FastAPI backend

## Cấu trúc dự án

```text
frontend/
├── app.py              # Entry point
├── components/
│   ├── chat.py         # Chat component
│   └── sidebar.py      # Sidebar
├── utils/
│   └── api.py          # API client
└── requirements.txt
```

## Code chính

### app.py

```python
import streamlit as st
import requests

# Cấu hình trang
st.set_page_config(
    page_title="Trợ lý AI HaUI",
    page_icon="🤖",
    layout="wide",
)

# API endpoint
API_URL = "http://localhost:8000/api/chat"

# Khởi tạo session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "feedback" not in st.session_state:
    st.session_state.feedback = {}


def call_api(question: str) -> dict | None:
    """Gọi API backend."""
    try:
        response = requests.post(
            API_URL,
            json={"question": question},
            timeout=300,  # 5 phút
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        st.error("Server phản hồi quá chậm. Vui lòng thử lại.")
    except requests.exceptions.ConnectionError:
        st.error("Không kết nối được server. Kiểm tra backend đã chạy chưa.")
    except Exception as e:
        st.error(f"Lỗi: {str(e)}")
    return None


def render_sources(sources: list[dict]) -> None:
    """Hiển thị danh sách nguồn tham khảo."""
    if not sources:
        return
    
    with st.expander(f"Nguồn tham khảo ({len(sources)} chunks)"):
        for i, src in enumerate(sources, 1):
            ma_vb = src.get("ma_van_ban", "N/A")
            dieu = src.get("dieu", "N/A")
            khoan = src.get("khoan", "N/A")
            ten_vb = src.get("ten_van_ban", "")
            distance = src.get("distance", 0)
            
            st.markdown(
                f"**{i}. [{ma_vb}]** - Điều {dieu}, Khoản {khoan}  \n"
                f"*{ten_vb}*  \n"
                f"Độ liên quan: `{1 - distance:.2%}`"
            )


def render_feedback(msg_index: int) -> None:
    """Hiển thị nút feedback."""
    col1, col2, col3 = st.columns([1, 1, 8])
    
    with col1:
        if st.button("Hữu ích", key=f"like_{msg_index}"):
            st.session_state.feedback[msg_index] = "like"
            st.success("Cảm ơn feedback!")
    
    with col2:
        if st.button("Chưa đúng", key=f"dislike_{msg_index}"):
            st.session_state.feedback[msg_index] = "dislike"
            st.warning("Cảm ơn, chúng tôi sẽ cải thiện!")


# SIDEBAR
with st.sidebar:
    st.title("Trợ lý AI HaUI")
    st.markdown("---")
    
    st.markdown("### Câu hỏi gợi ý")
    suggestions = [
        "Điều kiện tốt nghiệp thạc sĩ là gì?",
        "Thời gian đào tạo thạc sĩ là bao lâu?",
        "Học viên bị kỷ luật khi nào?",
        "Thủ tục xin nghỉ học tạm thời?",
    ]
    
    for suggestion in suggestions:
        if st.button(suggestion, use_container_width=True):
            st.session_state.pending_question = suggestion
    
    st.markdown("---")
    st.markdown("### Thông tin")
    st.caption("Phiên bản: 1.0.0")
    st.caption("Dữ liệu: Quy chế HaUI 2020-2024")
    
    if st.button("Xóa lịch sử chat"):
        st.session_state.messages = []
        st.session_state.feedback = {}
        st.rerun()


# MAIN CHAT
st.title("Trợ lý AI tra cứu quy chế")
st.caption("Hỏi bất kỳ điều gì về quy chế, quy định của trường")

# Hiển thị lịch sử chat
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        if msg["role"] == "assistant":
            if "sources" in msg:
                render_sources(msg["sources"])
            render_feedback(i)

# Input
user_input = st.chat_input("Nhập câu hỏi của bạn...")

# Xử lý câu hỏi từ suggestion
if "pending_question" in st.session_state:
    user_input = st.session_state.pending_question
    del st.session_state.pending_question

if user_input:
    # Hiển thị câu hỏi
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Gọi API
    with st.chat_message("assistant"):
        with st.spinner("Đang tra cứu..."):
            result = call_api(user_input)
        
        if result:
            st.markdown(result["answer"])
            render_sources(result.get("sources", []))
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": result["answer"],
                "sources": result.get("sources", []),
            })
        else:
            st.error("Không thể trả lời. Vui lòng thử lại.")
    
    st.rerun()
```

### utils/api.py

```python
import requests

API_URL = "http://localhost:8000/api/chat"


class RAGClient:
    def __init__(self, base_url: str = API_URL):
        self.base_url = base_url
    
    def chat(self, question: str, timeout: int = 300) -> dict:
        """Gửi câu hỏi và nhận câu trả lời."""
        response = requests.post(
            self.base_url,
            json={"question": question},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    
    def health_check(self) -> bool:
        """Kiểm tra backend còn sống không."""
        try:
            response = requests.get(
                self.base_url.replace("/chat", "/"),
                timeout=5,
            )
            return response.status_code == 200
        except Exception:
            return False
```

### CSS tùy chỉnh

```python
st.markdown("""
<style>
    /* Chat message */
    .stChatMessage {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
    }
    
    /* User message */
    .stChatMessage[data-testid="user-message"] {
        background-color: #e3f2fd;
    }
    
    /* Assistant message */
    .stChatMessage[data-testid="assistant-message"] {
        background-color: #f5f5f5;
    }
    
    /* Citation expander */
    .streamlit-expanderHeader {
        font-size: 0.9rem;
        color: #1976d2;
    }
</style>
""", unsafe_allow_html=True)
```

### Chạy Streamlit

```bash
pip install streamlit requests
streamlit run app.py
```

Mở trình duyệt: `http://localhost:8501`

### Deploy

#### Streamlit Cloud (Miễn phí)
1. Push code lên GitHub
2. Vào https://share.streamlit.io
3. Kết nối repo
4. Deploy

#### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

## Lưu ý quan trọng

### Session state
- Phải dùng `st.session_state` để lưu lịch sử chat.
- Không dùng biến global (sẽ mất khi rerun).
- Phải dùng `st.rerun()` sau khi update state.

### API call
- Phải set timeout dài (300s) vì RAG chậm.
- Phải xử lý các exception: `Timeout`, `ConnectionError`.
- Phải hiển thị trạng thái "đang xử lý".

### UI/UX
- Nên hiển thị nguồn tham khảo dạng expandable.
- Nên có nút feedback (like/dislike).
- Nên có câu hỏi gợi ý ở sidebar.
- Nên có nút xóa lịch sử chat.

### Performance
- Nên cache kết quả bằng `@st.cache_data`.
- Không gọi API trong vòng lặp.
- Nên dùng `st.spinner()` để hiển thị trạng thái.

## Thiết kế

- **Bắt buộc:** Không dùng chuỗi ký tự phân cách dài như `==============================================================================` để comment và note trong code.
- Sử dụng `#` để note.
- Thiết kế giao diện không cho phép sử dụng chuỗi ký tự `=` để trang trí; phải căn chỉnh kích thước phù hợp với khung hình và tạo ra giao diện đẹp nhất có thể.
- Không sử dụng icon dưới mọi hình thức trong code trừ khi được yêu cầu rõ ràng.
