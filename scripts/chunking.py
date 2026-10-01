# ============================================================
# BỘ CODE CHUNKING VĂN BẢN PHÁP LÝ - DÙNG EASYOCR
# Dự án: Trợ lý AI tra cứu quy chế - Trường ĐH Công nghiệp Hà Nội
# ============================================================

import os
import re
import json
import pdfplumber
import pymupdf
import numpy as np
import easyocr
from datetime import datetime
from pathlib import Path


# ============================================================
# PHẦN 1: CẤU HÌNH
# ============================================================

INPUT_DIR = "./data/raw_pdf"
OUTPUT_DIR = "./data/output_json"
OCR_CACHE_DIR = "./data/ocr_cache"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(OCR_CACHE_DIR, exist_ok=True)

# Khởi tạo EasyOCR (chỉ 1 lần)
print("🔧 Đang khởi tạo EasyOCR (lần đầu sẽ tải model ~100MB)...")
ocr_reader = easyocr.Reader(['vi', 'en'], gpu=False, verbose=False)
print("✓ EasyOCR đã sẵn sàng\n")


# ============================================================
# PHẦN 2: KIỂM TRA PDF CÓ TEXT LAYER HAY KHÔNG
# ============================================================

def has_text_layer(pdf_path, min_chars_per_page=50):
    """
    Kiểm tra PDF có text layer (PDF gõ) hay là PDF scan (ảnh).
    - Nếu trung bình mỗi trang có > 50 ký tự → Có text layer
    - Nếu < 50 ký tự → Là PDF scan
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_chars = 0
            num_pages = len(pdf.pages)
            
            for page in pdf.pages[:3]:
                text = page.extract_text() or ""
                total_chars += len(text.strip())
            
            avg_chars = total_chars / min(3, num_pages)
            return avg_chars > min_chars_per_page
    
    except Exception as e:
        print(f"   ⚠️  Lỗi kiểm tra text layer: {e}")
        return False


# ============================================================
# PHẦN 3: OCR PDF SCAN BẰNG EASYOCR
# ============================================================

def ocr_pdf_with_easyocr(pdf_path, dpi=300):
    """
    OCR file PDF scan bằng EasyOCR.
    Sử dụng PyMuPDF để render PDF thành ảnh.
    """
    filename = os.path.basename(pdf_path)
    cache_path = os.path.join(OCR_CACHE_DIR, filename.replace(".pdf", ".txt"))
    
    # --- Kiểm tra cache ---
    if os.path.exists(cache_path):
        print(f"   ⚡ Dùng cache OCR có sẵn")
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()
    
    print(f"   🔍 Đang OCR (có thể mất 1-3 phút)...")
    
    try:
        # --- Bước 1: Mở PDF bằng PyMuPDF ---
        doc = pymupdf.open(pdf_path)
        print(f"   📄 Đã mở PDF: {doc.page_count} trang")
        
        # Tính hệ số zoom để đạt DPI mong muốn
        zoom = dpi / 72
        mat = pymupdf.Matrix(zoom, zoom)
        
        full_text = ""
        
        # --- Bước 2: Lặp qua từng trang ---
        for page_num in range(doc.page_count):
            page = doc[page_num]
            
            # Render trang thành ảnh pixmap
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Chuyển pixmap thành numpy array
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n
            )
            
            # Nếu ảnh chỉ 1 kênh, chuyển thành 3 kênh
            if pix.n == 1:
                img_array = np.stack([img_array[:, :, 0]] * 3, axis=-1)
            
            # Nếu ảnh 4 kênh (RGBA), bỏ kênh alpha
            if pix.n == 4:
                img_array = img_array[:, :, :3]
            
            # --- Bước 3: Chạy OCR ---
            # detail=0: chỉ lấy text
            # paragraph=False: không gộp thành đoạn
            results = ocr_reader.readtext(img_array, detail=0, paragraph=False)
            
            # --- Bước 4: Ghép text ---
            if results:
                page_text = "\n".join(results)
                full_text += f"\n--- Trang {page_num + 1} ---\n{page_text}"
            
            # In tiến độ
            if (page_num + 1) % 5 == 0 or (page_num + 1) == doc.page_count:
                print(f"   ⏳ Đã OCR {page_num + 1}/{doc.page_count} trang")
        
        doc.close()
        
        # --- Bước 5: Lưu cache ---
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        
        print(f"   ✓ OCR xong: {len(full_text)} ký tự")
        return full_text
    
    except Exception as e:
        print(f"   ❌ Lỗi OCR: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================
# PHẦN 4: ĐỌC PDF THÔNG MINH
# ============================================================

def extract_text_smart(pdf_path):
    """
    Đọc PDF thông minh:
    - Nếu có text layer → Dùng pdfplumber (nhanh)
    - Nếu là PDF scan → Dùng PyMuPDF + EasyOCR
    """
    if has_text_layer(pdf_path):
        print(f"   📝 PDF có text layer → Đọc trực tiếp")
        try:
            full_text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text += "\n" + text
            return full_text
        except Exception as e:
            print(f"   ❌ Lỗi đọc text layer: {e}")
            return None
    else:
        print(f"   🖼️  PDF scan → Chuyển sang OCR")
        return ocr_pdf_with_easyocr(pdf_path)


# ============================================================
# PHẦN 5: LÀM SẠCH VĂN BẢN SAU OCR
# ============================================================

def clean_ocr_text(text):
    """
    Làm sạch văn bản sau OCR:
    - Xóa marker trang
    - Sửa lỗi OCR phổ biến tiếng Việt
    - Chuẩn hóa khoảng trắng
    """
    if not text:
        return text
    
    # --- Xóa marker trang ---
    text = re.sub(r"--- Trang \d+ ---", "", text)
    
    # --- Sửa lỗi OCR phổ biến ---
    replacements = {
        r"\bdiều\b": "điều",
        r"\bdiểm\b": "điểm",
        r"\bdối\b": "đối",
        r"\bdược\b": "được",
        r"\bdào\b": "đào",
        r"\bdại\b": "đại",
        r"\bdơn\b": "đơn",
        r"\bdủ\b": "đủ",
        r"\bdịnh\b": "định",
        r"\bthòi\b": "thời",
        r"\bthòa\b": "thỏa",
        r"\btrưồng\b": "trường",
        r"\btrưòng\b": "trường",
        r"\bTrưòng\b": "Trường",
        r"\bTrưồng\b": "Trường",
        r"\bquyét\b": "quyết",
        r"\bQuyét\b": "Quyết",
        r"\bquy dinh\b": "quy định",
        r"\bQuy dinh\b": "Quy định",
    }
    
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text)
    
    # --- Chuẩn hóa khoảng trắng ---
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    # --- Xóa ký tự điều khiển lạ ---
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    
    return text.strip()


# ============================================================
# PHẦN 6: TRÍCH XUẤT METADATA TỰ ĐỘNG
# ============================================================

def extract_metadata(text, filename):
    """Tự động trích xuất metadata từ nội dung văn bản."""
    
    metadata = {
        "ten_file": filename,
        "ma_van_ban": None,
        "ngay_ban_hanh": None,
        "loai_van_ban": None,
        "ten_van_ban": None,
        "co_quan_ban_hanh": "Trường Đại học Công nghiệp Hà Nội",
        "tinh_trang_hieu_luc": True,
        "ngay_xu_ly": datetime.now().strftime("%Y-%m-%d"),
    }
    
    # --- Số văn bản ---
    so_match = re.search(r"Số:\s*(\d+)\s*/\s*([A-ZĐ\-]+)", text)
    if so_match:
        metadata["ma_van_ban"] = f"{so_match.group(1)}/{so_match.group(2)}"
    
    # --- Ngày ban hành ---
    ngay_match = re.search(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", text)
    if ngay_match:
        day, month, year = ngay_match.groups()
        metadata["ngay_ban_hanh"] = f"{year}-{int(month):02d}-{int(day):02d}"
    else:
        ngay_match = re.search(r"ngày\s+(\d{1,2})/(\d{1,2})/(\d{4})", text)
        if ngay_match:
            day, month, year = ngay_match.groups()
            metadata["ngay_ban_hanh"] = f"{year}-{int(month):02d}-{int(day):02d}"
    
    # --- Loại văn bản ---
    header = text[:1500].upper()
    for keyword, loai in [
        ("QUYẾT ĐỊNH", "Quyết định"),
        ("QUY CHẾ", "Quy chế"),
        ("THÔNG TƯ", "Thông tư"),
        ("QUY ĐỊNH", "Quy định"),
        ("THÔNG BÁO", "Thông báo"),
        ("CÔNG VĂN", "Công văn"),
        ("NGHỊ ĐỊNH", "Nghị định"),
    ]:
        if keyword in header:
            metadata["loai_van_ban"] = loai
            break
    
    # --- Tên văn bản ---
    ten_patterns = [
        r"Ban hành\s+(?:kèm theo\s+Quyết định này\s+)?(.+?)(?:\n|tại Trường)",
        r"Về việc\s+(.+?)(?:\n|\.)",
        r"QUY CHẾ\s*\n\s*(.+?)(?:\n|tại Trường)",
    ]
    for pattern in ten_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            ten = re.sub(r"\s+", " ", match.group(1).strip())
            if 10 < len(ten) < 200:
                metadata["ten_van_ban"] = ten
                break
    
    return metadata


# ============================================================
# PHẦN 7: CHUNKING THEO ĐIỀU/KHOẢN
# ============================================================

def chunk_legal_document(text, metadata_base):
    """Cắt văn bản theo cấu trúc Điều/Khoản."""
    chunks = []
    
    # Tách theo Điều
    dieu_pattern = r"(Điều\s+\d+\.)"
    parts = re.split(dieu_pattern, text)
    
    # Nếu không có cấu trúc Điều → Fallback
    if len(parts) < 3:
        print(f"   ⚠️  Không có cấu trúc Điều → Cắt theo đoạn")
        return chunk_by_paragraph(text, metadata_base)
    
    for i in range(1, len(parts), 2):
        dieu_title = parts[i].strip()
        dieu_content = parts[i+1].strip() if i+1 < len(parts) else ""
        
        dieu_match = re.search(r"\d+", dieu_title)
        dieu_number = dieu_match.group() if dieu_match else "?"
        
        # Tách theo Khoản
        khoan_parts = re.split(r"(?=\n\d+\.)", dieu_content)
        
        for khoan_text in khoan_parts:
            if not khoan_text.strip():
                continue
            
            khoan_match = re.match(r"\n?(\d+)\.", khoan_text)
            khoan_number = khoan_match.group(1) if khoan_match else "Mở đầu"
            
            # Nếu một Khoản quá dài (> 1500 ký tự), thực hiện sub-chunking có overlap để tối ưu embedding
            MAX_CHUNK_CHARS = 1500
            OVERLAP_CHARS = 150

            if len(chunk_content) <= MAX_CHUNK_CHARS:
                chunk_metadata = metadata_base.copy()
                chunk_metadata["dieu"] = dieu_number
                chunk_metadata["khoan"] = khoan_number
                chunks.append({
                    "content": chunk_content,
                    "metadata": chunk_metadata
                })
            else:
                sub_parts = []
                start = 0
                while start < len(chunk_content):
                    end = start + MAX_CHUNK_CHARS
                    sub_text = chunk_content[start:end].strip()
                    if sub_text:
                        sub_parts.append(sub_text)
                    start += (MAX_CHUNK_CHARS - OVERLAP_CHARS)

                for sub_idx, sub_c in enumerate(sub_parts, start=1):
                    chunk_metadata = metadata_base.copy()
                    chunk_metadata["dieu"] = dieu_number
                    chunk_metadata["khoan"] = khoan_number
                    chunk_metadata["sub_index"] = sub_idx
                    chunks.append({
                        "content": sub_c,
                        "metadata": chunk_metadata
                    })
    
    return chunks


def chunk_by_paragraph(text, metadata_base, chunk_size=800):
    """Fallback: Cắt theo đoạn văn."""
    chunks = []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    
    buffer = ""
    for para in paragraphs:
        if len(buffer) + len(para) < chunk_size:
            buffer += "\n" + para
        else:
            if buffer:
                chunks.append({
                    "content": buffer.strip(),
                    "metadata": {**metadata_base, "loai_chunk": "doan_van"}
                })
            buffer = para
    
    if buffer:
        chunks.append({
            "content": buffer.strip(),
            "metadata": {**metadata_base, "loai_chunk": "doan_van"}
        })
    
    return chunks


# ============================================================
# PHẦN 8: XỬ LÝ MỘT FILE
# ============================================================

def process_single_file(pdf_path):
    """Xử lý một file PDF: Đọc → OCR (nếu cần) → Làm sạch → Chunking."""
    filename = os.path.basename(pdf_path)
    print(f"\n📄 Đang xử lý: {filename}")
    
    # 1. Đọc PDF
    text = extract_text_smart(pdf_path)
    if not text or len(text) < 100:
        print(f"   ❌ File rỗng hoặc OCR thất bại")
        return None
    
    # 2. Làm sạch văn bản
    text = clean_ocr_text(text)
    print(f"   ✓ Sau khi làm sạch: {len(text)} ký tự")
    
    # 3. Trích xuất metadata
    metadata = extract_metadata(text, filename)
    print(f"   ✓ Metadata: Mã={metadata['ma_van_ban']}, Ngày={metadata['ngay_ban_hanh']}")
    
    # 4. Chunking
    chunks = chunk_legal_document(text, metadata)
    print(f"   ✓ Đã cắt thành {len(chunks)} chunks")
    
    return chunks


# ============================================================
# PHẦN 9: HÀM CHÍNH
# ============================================================

def process_all_files():
    """Quét tất cả file PDF trong thư mục và xử lý."""
    print("=" * 60)
    print("🚀 BẮT ĐẦU XỬ LÝ HÀNG LOẠT FILE PDF (EASYOCR)")
    print("=" * 60)
    
    pdf_files = list(Path(INPUT_DIR).glob("*.pdf"))
    
    if not pdf_files:
        print(f"❌ Không tìm thấy file PDF nào trong {INPUT_DIR}")
        return
    
    print(f"📁 Tìm thấy {len(pdf_files)} file PDF\n")
    
    all_chunks = []
    summary = []
    
    for idx, pdf_path in enumerate(pdf_files, 1):
        print(f"\n[{idx}/{len(pdf_files)}] " + "=" * 50)
        chunks = process_single_file(str(pdf_path))
        
        if chunks:
            # Lưu riêng từng file
            output_name = pdf_path.stem + ".json"
            output_path = os.path.join(OUTPUT_DIR, output_name)
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)
            
            print(f"   💾 Đã lưu: {output_path}")
            
            all_chunks.extend(chunks)
            summary.append({
                "file": pdf_path.name,
                "so_chunk": len(chunks),
                "trang_thai": "✓"
            })
        else:
            summary.append({
                "file": pdf_path.name,
                "so_chunk": 0,
                "trang_thai": "✗"
            })
    
    # Lưu file tổng hợp
    all_output_path = os.path.join(OUTPUT_DIR, "all_chunks.json")
    with open(all_output_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)
    
    # Báo cáo tổng kết
    print("\n" + "=" * 60)
    print("📊 BÁO CÁO TỔNG KẾT")
    print("=" * 60)
    print(f"Tổng file xử lý: {len(summary)}")
    print(f"Tổng chunk: {len(all_chunks)}")
    print(f"File tổng hợp: {all_output_path}\n")
    for item in summary:
        print(f"  [{item['trang_thai']}] {item['file']}: {item['so_chunk']} chunks")


# ============================================================
# CHẠY
# ============================================================

if __name__ == "__main__":
    process_all_files()