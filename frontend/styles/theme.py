"""Định nghĩa giao diện, phong cách và hệ thống CSS linh hoạt hỗ trợ chế độ Sáng / Tối.

Hỗ trợ chuyển đổi mượt mà giữa:
- Chế độ Sáng (Light Mode): Nền trắng thanh lịch, thẻ chứng cứ rõ ràng, điểm nhấn xanh HaUI.
- Chế độ Tối (Dark Mode): Nền Slate Navy sâu, độ tương phản cao, chống lóa và tương thích hoàn toàn khi trình duyệt bật dark mode.
"""

import base64
from pathlib import Path
from typing import Any
import streamlit as st

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "haui_logo.png"


def get_logo_base64() -> str:
    """Trả về chuỗi data:image/png;base64 của logo HaUI để nhúng trực tiếp vào HTML."""
    if LOGO_PATH.exists():
        with open(LOGO_PATH, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"
    return ""

# Các token màu sắc Light Mode
LIGHT_THEME = {
    "bg_page": "#F8FAFC",
    "bg_sidebar": "#FFFFFF",
    "bg_card": "#FFFFFF",
    "border_color": "#E5E7EB",
    "text_main": "#111827",
    "text_muted": "#4B5563",
    "text_subtle": "#9CA3AF",
    "primary_blue": "#185EE0",
    "primary_blue_hover": "#134BBA",
    "active_bg": "#EEF3FF",
    "active_border": "#BFDBFE",
    "tag_type_bg": "#EFF6FF",
    "tag_type_text": "#1E40AF",
    "tag_clause_bg": "#F3F4F6",
    "tag_clause_text": "#4B5563",
    "info_box_bg": "#F0F6FF",
    "info_box_border": "#BFDBFE",
    "info_box_text": "#1E40AF",
    "input_bg": "#FFFFFF",
    "input_border": "#D1D5DB",
    "watermark_opacity": "0.08",
}

# Các token màu sắc Dark Mode
DARK_THEME = {
    "bg_page": "#0B0F17",
    "bg_sidebar": "#111827",
    "bg_card": "#161F30",
    "border_color": "#253248",
    "text_main": "#F8FAFC",
    "text_muted": "#94A3B8",
    "text_subtle": "#64748B",
    "primary_blue": "#2563EB",
    "primary_blue_hover": "#1D4ED8",
    "active_bg": "#1E293B",
    "active_border": "#3B82F6",
    "tag_type_bg": "#1E293B",
    "tag_type_text": "#93C5FD",
    "tag_clause_bg": "#1F2937",
    "tag_clause_text": "#CBD5E1",
    "info_box_bg": "#111E33",
    "info_box_border": "#1E3A8A",
    "info_box_text": "#93C5FD",
    "input_bg": "#161F30",
    "input_border": "#2E3F5B",
    "watermark_opacity": "0.04",
}


def get_theme_css(mode: str = "dark") -> str:
    """
    Sinh chuỗi CSS định dạng hoàn chỉnh theo giao diện Tối (Dark Mode) mặc định.

    Args:
        mode: Mặc định "dark".

    Returns:
        str: Chuỗi HTML <style> áp dụng lên ứng dụng.
    """
    t = DARK_THEME

    return f"""
<style>
/* 1. Thiết lập biến màu gốc (CSS Variables) */
:root {{
    --bg-page: {t["bg_page"]};
    --bg-sidebar: {t["bg_sidebar"]};
    --bg-card: {t["bg_card"]};
    --border-color: {t["border_color"]};
    --text-main: {t["text_main"]};
    --text-muted: {t["text_muted"]};
    --text-subtle: {t["text_subtle"]};
    --primary-blue: {t["primary_blue"]};
    --primary-blue-hover: {t["primary_blue_hover"]};
    --active-bg: {t["active_bg"]};
    --active-border: {t["active_border"]};
    --tag-type-bg: {t["tag_type_bg"]};
    --tag-type-text: {t["tag_type_text"]};
    --tag-clause-bg: {t["tag_clause_bg"]};
    --tag-clause-text: {t["tag_clause_text"]};
    --info-box-bg: {t["info_box_bg"]};
    --info-box-border: {t["info_box_border"]};
    --info-box-text: {t["info_box_text"]};
    --input-bg: {t["input_bg"]};
    --input-border: {t["input_border"]};
}}

/* Ghi đè toàn bộ nền ứng dụng Streamlit */
html, body, .stApp, [data-testid="stAppViewContainer"] {{
    background-color: var(--bg-page) !important;
    color: var(--text-main) !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
}}

/* Ẩn bớt các thanh header mặc định của Streamlit */
#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden;}}
header[data-testid="stHeader"] {{
    background-color: var(--bg-page) !important;
}}

/* Khung Sidebar */
section[data-testid="stSidebar"] {{
    background-color: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border-color) !important;
}}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
    color: var(--text-main) !important;
}}

/* 2. Top Navigation Bar */
.topbar-wrapper {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 0 16px 0;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 20px;
}}
.topbar-left {{
    display: flex;
    align-items: center;
    gap: 12px;
}}
.topbar-crest {{
    width: 38px;
    height: 38px;
    border-radius: 8px;
    background-color: #0B2545;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #FACC15;
    font-weight: 800;
    font-size: 0.95rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}}
.topbar-brand-title {{
    font-size: 1.15rem;
    font-weight: 800;
    color: var(--text-main);
    line-height: 1.2;
    margin: 0;
}}
.topbar-brand-title span {{
    font-weight: 500;
    color: var(--text-muted);
    margin-left: 6px;
}}
.topbar-brand-sub {{
    font-size: 0.82rem;
    color: var(--text-muted);
    margin: 2px 0 0 0;
}}
.topbar-right {{
    display: flex;
    align-items: center;
    gap: 16px;
}}
.status-badge-good {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.82rem;
    font-weight: 500;
    color: #10B981;
}}
.status-badge-dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background-color: #10B981;
}}

/* 3. Nút bấm chính và thẻ Sidebar */
.stButton > button {{
    border-radius: 8px !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    border: 1px solid var(--border-color) !important;
    background-color: var(--bg-card) !important;
    color: var(--text-main) !important;
    transition: all 0.15s ease-in-out !important;
}}
.stButton > button:hover {{
    border-color: var(--primary-blue) !important;
    color: var(--primary-blue) !important;
}}
.stButton > button[kind="primary"] {{
    background-color: var(--primary-blue) !important;
    color: #FFFFFF !important;
    border: none !important;
}}
.stButton > button[kind="primary"]:hover {{
    background-color: var(--primary-blue-hover) !important;
}}

/* Nút bấm gợi ý câu hỏi trong Empty State căn trái thanh lịch */
div[data-testid="column"] .stButton > button {{
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 12px 14px !important;
    line-height: 1.4 !important;
}}

.sidebar-section-heading {{
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-subtle);
    margin: 16px 0 8px 4px;
}}

/* 4. Empty State Trung Tâm */
.empty-state-wrapper {{
    text-align: center;
    max-width: 660px;
    margin: 24px auto 16px auto;
    position: relative;
    z-index: 2;
}}
.empty-illustration-box {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 64px;
    height: 64px;
    border-radius: 16px;
    background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
    margin-bottom: 16px;
    box-shadow: 0 4px 12px rgba(24, 94, 224, 0.08);
}}
.empty-headline {{
    font-size: 1.6rem;
    font-weight: 800;
    color: var(--text-main);
    letter-spacing: -0.015em;
    margin-bottom: 8px;
}}
.empty-subheadline {{
    font-size: 0.92rem;
    color: var(--text-muted);
    line-height: 1.55;
    margin-bottom: 24px;
}}
.search-input-pill {{
    display: flex;
    align-items: center;
    background-color: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 10px 16px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    margin-bottom: 8px;
}}
.search-hint {{
    font-size: 0.76rem;
    color: var(--text-subtle);
    margin-bottom: 28px;
}}
.suggestion-title {{
    font-size: 0.88rem;
    font-weight: 700;
    color: var(--text-main);
    text-align: left;
    margin-bottom: 12px;
}}

/* 5. Evidence Panel (Cột Phải) */
.evidence-header-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.98rem;
    font-weight: 800;
    color: var(--text-main);
    margin-bottom: 2px;
}}
.evidence-count-sub {{
    font-size: 0.82rem;
    color: var(--text-muted);
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-color);
}}
.evidence-card {{
    background-color: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    padding: 14px;
    margin-bottom: 12px;
    transition: all 0.15s ease;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02);
}}
.evidence-card:hover {{
    border-color: var(--primary-blue);
    box-shadow: 0 3px 8px rgba(0,0,0,0.05);
}}
.evidence-card-selected {{
    border: 2px solid var(--primary-blue);
    background-color: var(--active-bg);
}}
.card-header-line {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}}
.num-circle {{
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background-color: #1E3A8A;
    color: #FFFFFF;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 700;
}}
.card-doc-title {{
    font-size: 0.92rem;
    font-weight: 700;
    color: var(--text-main);
    flex-grow: 1;
    margin-left: 8px;
}}
.card-tags-row {{
    display: flex;
    gap: 6px;
    margin-bottom: 10px;
}}
.pill-tag {{
    font-size: 0.75rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 6px;
    background-color: var(--tag-type-bg);
    color: var(--tag-type-text);
}}
.pill-clause {{
    font-size: 0.75rem;
    font-weight: 500;
    padding: 2px 8px;
    border-radius: 6px;
    background-color: var(--tag-clause-bg);
    color: var(--tag-clause-text);
}}
.card-quote-snippet {{
    font-size: 0.83rem;
    color: var(--text-muted);
    line-height: 1.5;
    font-style: italic;
}}

/* Banner xanh hướng dẫn ở đáy Evidence panel */
.info-footer-box {{
    background-color: var(--info-box-bg);
    border: 1px solid var(--info-box-border);
    border-radius: 10px;
    padding: 12px 14px;
    margin-top: 14px;
    display: flex;
    gap: 10px;
    align-items: flex-start;
}}
.info-footer-title {{
    font-size: 0.82rem;
    font-weight: 700;
    color: var(--info-box-text);
    margin-bottom: 2px;
}}
.info-footer-sub {{
    font-size: 0.76rem;
    color: var(--info-box-text);
    opacity: 0.9;
    line-height: 1.4;
}}

/* Watermark hình tòa nhà HaUI ở đáy trang */
.watermark-container {{
    position: fixed;
    bottom: 0;
    left: 260px;
    right: 340px;
    height: 140px;
    opacity: {t["watermark_opacity"]};
    pointer-events: none;
    z-index: 0;
    background-position: center bottom;
    background-repeat: no-repeat;
    background-size: contain;
}}

/* 6. Định dạng khung thanh nhập câu hỏi và chân trang */
div[data-testid="stBottom"] {{
    background-color: var(--bg-page) !important;
    background: var(--bg-page) !important;
}}

div[data-testid="stBottom"] > div,
div[data-testid="stBottom"] [data-testid="stVerticalBlock"],
div[data-testid="stBottom"] [data-testid="stHorizontalBlock"] {{
    background-color: transparent !important;
    background: transparent !important;
}}

div[data-testid="stChatInput"],
.stChatInput,
div[data-testid="stChatInputContainer"],
div[data-testid="stChatFloatingInputContainer"] {{
    background-color: transparent !important;
    background: transparent !important;
}}

/* Khung viền và màu nền của DUY NHẤT thanh câu hỏi - CỐ ĐỊNH NỀN XÁM, CHỮ TRẮNG */
div[data-testid="stChatInput"] > div,
.stChatInput > div {{
    background-color: #262730 !important;
    background: #262730 !important;
    border: 1.5px solid #3F444E !important;
    border-radius: 12px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12) !important;
    transition: all 0.2s ease-in-out !important;
}}

/* Hiệu ứng khi focus vào thanh câu hỏi */
div[data-testid="stChatInput"] > div:focus-within,
.stChatInput > div:focus-within {{
    border-color: #185EE0 !important;
    box-shadow: 0 0 0 2px rgba(24, 94, 224, 0.35) !important;
}}

/* Khử triệt để mọi nền và viền phụ của các thẻ div lồng bên trong stChatInput */
div[data-testid="stChatInput"] > div div,
.stChatInput > div div,
div[data-testid="stChatInput"] [data-baseweb],
.stChatInput [data-baseweb] {{
    background-color: transparent !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}}

/* Màu chữ và placeholder bên trong thanh câu hỏi - CỐ ĐỊNH CHỮ TRẮNG */
div[data-testid="stChatInput"] textarea,
.stChatInput textarea {{
    background-color: transparent !important;
    background: transparent !important;
    color: #FFFFFF !important;
    font-size: 0.95rem !important;
    line-height: 1.5 !important;
    caret-color: #FFFFFF !important;
    border: none !important;
    box-shadow: none !important;
}}

div[data-testid="stChatInput"] textarea::placeholder,
.stChatInput textarea::placeholder {{
    color: #9CA3AF !important;
    opacity: 0.85 !important;
}}

/* Nút gửi màu đỏ HaUI */
div[data-testid="stChatInput"] button,
.stChatInput button,
button[data-testid="stChatInputSubmitButton"] {{
    background-color: #E02424 !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    transition: background-color 0.15s ease !important;
}}

div[data-testid="stChatInput"] button:hover,
.stChatInput button:hover,
button[data-testid="stChatInputSubmitButton"]:hover {{
    background-color: #B91C1C !important;
}}

div[data-testid="stChatInput"] button svg,
.stChatInput button svg,
button[data-testid="stChatInputSubmitButton"] svg {{
    fill: #FFFFFF !important;
    stroke: #FFFFFF !important;
    color: #FFFFFF !important;
}}

div[data-testid="stChatInput"] button:disabled,
.stChatInput button:disabled,
button[data-testid="stChatInputSubmitButton"]:disabled {{
    background-color: var(--border-color) !important;
    color: var(--text-subtle) !important;
    opacity: 0.4 !important;
}}

div[data-testid="stChatInput"] button:disabled svg,
.stChatInput button:disabled svg,
button[data-testid="stChatInputSubmitButton"]:disabled svg {{
    fill: var(--text-subtle) !important;
    stroke: var(--text-subtle) !important;
    color: var(--text-subtle) !important;
}}

/* 7. Định dạng dòng tin nhắn hội thoại */
.message-bubble-user {{
    background-color: var(--active-bg);
    border: 1px solid var(--active-border);
    border-radius: 12px;
    padding: 12px 16px;
    margin-bottom: 16px;
    color: var(--text-main);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
}}

.message-role-label {{
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--primary-blue);
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}

.message-assistant-body {{
    font-size: 0.95rem;
    line-height: 1.65;
    color: var(--text-main);
    margin-bottom: 12px;
}}

.fallback-banner {{
    background-color: var(--info-box-bg);
    border: 1px solid var(--info-box-border);
    color: var(--info-box-text);
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.85rem;
    margin-bottom: 12px;
    line-height: 1.5;
}}

/* 8. Màu chữ Markdown và thanh tìm kiếm ở màn hình ngoài (Empty State Search Bar) - CỐ ĐỊNH NỀN XÁM, CHỮ TRẮNG */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] li {{
    color: var(--text-main);
}}

div[data-testid="stTextInput"] div[data-baseweb="input"],
div[data-testid="stTextInput"] div[data-baseweb="base-input"] {{
    background-color: #262730 !important;
    background: #262730 !important;
    border: 1.5px solid #3F444E !important;
    border-radius: 12px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12) !important;
    transition: all 0.2s ease-in-out !important;
}}

div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
div[data-testid="stTextInput"] div[data-baseweb="base-input"]:focus-within {{
    border-color: #185EE0 !important;
    box-shadow: 0 0 0 2px rgba(24, 94, 224, 0.35) !important;
}}

div[data-testid="stTextInput"] input {{
    background-color: transparent !important;
    background: transparent !important;
    color: #FFFFFF !important;
    caret-color: #FFFFFF !important;
    border: none !important;
    font-size: 0.95rem !important;
    border-radius: 12px !important;
}}

div[data-testid="stTextInput"] input::placeholder {{
    color: #9CA3AF !important;
    opacity: 0.85 !important;
}}

.stTextArea textarea {{
    background-color: var(--input-bg) !important;
    border: 1px solid var(--input-border) !important;
    color: var(--text-main) !important;
    border-radius: 8px !important;
}}

/* 9. Bảng nguồn tham khảo (Evidence Panel) di chuyển cuộn dính cố định (Sticky) */
div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2) {{
    position: sticky !important;
    top: 55px !important;
    align-self: flex-start !important;
    max-height: calc(100vh - 75px) !important;
    overflow-y: auto !important;
    padding-right: 6px !important;
    scrollbar-width: thin !important;
    scrollbar-color: #2E3F5B transparent !important;
}}

div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2)::-webkit-scrollbar {{
    width: 5px !important;
}}

div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2)::-webkit-scrollbar-track {{
    background: transparent !important;
}}

div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2)::-webkit-scrollbar-thumb {{
    background: #2E3F5B !important;
    border-radius: 4px !important;
}}

.evidence-details {{
    margin-top: 8px;
    font-size: 0.8rem;
}}

.evidence-details summary {{
    cursor: pointer;
    color: var(--primary-blue);
    font-weight: 600;
    user-select: none;
    outline: none;
    margin-top: 4px;
}}

.evidence-details summary:hover {{
    text-decoration: underline;
}}

.evidence-full-text {{
    margin-top: 6px;
    padding: 8px 10px;
    background-color: var(--active-bg);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 0.8rem;
    line-height: 1.5;
    color: var(--text-main);
    white-space: pre-wrap;
}}
</style>
"""


def apply_theme(mode: str = "dark") -> None:
    """
    Áp dụng CSS cho ứng dụng theo giao diện Tối (Dark Mode).

    Args:
        mode: Mặc định "dark".
    """
    css_content = get_theme_css(mode="dark")
    st.markdown(css_content, unsafe_allow_html=True)
