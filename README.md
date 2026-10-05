# HAUI RAG Assistant - Huong Dan Cai Dat Va Khoi Chay He Thong

He thong Tro ly AI tra cuu quy che, quy dinh va van ban noi bo Truong Dai hoc Cong nghiep Ha Noi (HaUI).
Kien truc RAG (Retrieval-Augmented Generation) ket hop PostgreSQL (pgvector) va mo hinh ngon ngu lon (Local LLM qua Ollama hoac Cloud LLM qua Google Gemini).

---

## 1. Tong Quan Va Kien Truc

He thong duoc thiet ke theo mo hinh Clean Architecture gom cac thanh phan:
- **Core Engine (haui_rag):** Xu ly embedding cau hoi (Gemini Embedding 001 - 3072 chieu), vector retrieval (cosine distance voi halfvec tren PostgreSQL), sinh cau tra loi co trich dan (Qwen / Gemma / Gemini).
- **Backend API (FastAPI):** Expose cac endpoint REST API (`POST /api/chat`, quan ly lich su hoi thoai, luu log truy van va feedback nguoi dung). Tu dong thuc thi migration database khi khoi dong.
- **Frontend UI (Streamlit):** Giao dien chat truc quan, hien thi trich dan nguon van ban, goi y cau hoi va ho tro danh gia phan hoi.
- **Master Runner & Automation Scripts:** Cac script batch (`.bat`) giup tu dong hoa toan bo quy trinh thiet lap moi truong, tai mo hinh va khoi dong ung dung.

---

## 2. Yeu Cau He Thong Va Phan Mem Tien Quyet

Truoc khi khoi chay he thong tren may moi, can cai dat cac cong cu nen tang sau:

### 2.1. Python 3.11 (Bat buoc)
- Khuyen nghi: **Python 3.11.9** (Khong dung Python 3.13 do khong tuong thich mot so thu vien C-extension).
- Khi cai dat tren Windows, bat buoc tich chon: `Add python.exe to PATH`.

### 2.2. PostgreSQL kem Extension pgvector
- Phien ban khuyen nghi: **PostgreSQL 16 hoac 18**.
- **pgvector (ban 0.8.x tro len):** Bat buoc phai cai extension nay cho PostgreSQL de ho tro kieu du lieu `vector` va index `halfvec`.
- Luu y thiet lap cong mac dinh la `5432` va ghi nho mat khau cua tai khoan `postgres`.

### 2.3. Ollama (Neu su dung Local LLM)
- Neu su dung mo hinh cuc bo tren GPU/CPU noi bo (khong ton phi API, bao mat du lieu), can cai dat Ollama:
  - Trang chu: https://ollama.com/download
  - Cau hinh phan cung toi thieu cho Local LLM: GPU co 4GB VRAM (nhu NVIDIA RTX 3050 Laptop) tro len, hoac CPU ho tro tap lenh AVX2 voi toi thieu 16GB RAM.

### 2.4. Google Gemini API Key (Bat buoc)
- Kể ca khi su dung Local LLM cho phan sinh cau tra loi, pipeline van su dung model `gemini-embedding-001` de tao vector truy van 3072 chieu dong bo voi du lieu vector trong database.
- Lay API key mien phi tai: https://aistudio.google.com/app/apikey

---

## 3. Chuan Bi Co So Du Lieu (PostgreSQL)

Git khong luu tru co so du lieu PostgreSQL. Vi vay tren may moi, can thiet lap database theo cac buoc sau:

### 3.1. Tao Database va kich hoat pgvector
Mo cong cu `psql` hoac `pgAdmin` va thuc thi cac cau lenh SQL sau:

```sql
CREATE DATABASE rag_haui;
\c rag_haui
CREATE EXTENSION IF NOT EXISTS vector;
```

### 3.2. Cau truc bang du lieu
Database `rag_haui` gom 2 nhom bang:
1. **Nhom bang nghiep vu ung dung:**
   - `conversations`, `messages`, `request_logs`, `feedback`, `schema_migrations`.
   - Nhom bang nay se **tu dong duoc tao** khi Backend FastAPI khoi dong lan dau thong qua co che Migration tu dong (`migrations/001_...` den `migrations/005_...`).
2. **Bang tri thuc vector (`documents`):**
   - Chuan du lieu: `id` (SERIAL PRIMARY KEY), `content` (TEXT), `metadata` (JSONB), `embedding` (vector(3072)).
   - Index tim kiem: HNSW voi `halfvec_cosine_ops` (`embedding::halfvec(3072)`).
   - Day la bang chua toan bo tri thuc 1.714 chunks quy che cua HaUI da duoc embedding san.

### 3.3. Nap du lieu vao bang documents khi sang may moi
Tren may goc da co du lieu, can thuc hien xuat (dump) bang `documents` va import vao may moi:

- **Xuat du lieu tren may cu:**
  ```bash
  pg_dump -U postgres -d rag_haui -t documents -F p -f documents_dump.sql
  ```
- **Nhap du lieu vao may moi:**
  ```bash
  psql -U postgres -d rag_haui -f documents_dump.sql
  ```
- **Kiem tra so luong ban ghi:**
  ```sql
  SELECT COUNT(*) FROM documents;
  -- Ket qua phai co 1.714 ban ghi
  ```

---

## 4. Cau Hinh Bien Moi Truong (.env)

Tai thu muc goc cua du an, sao chep file `.env.example` thanh `.env`:

```bash
copy .env.example .env
```

Mo file `.env` bang trinh soan thao va thiet lap cac thong so thuc te:

```ini
# Google Gemini API
GEMINI_API_KEY=AIzaSy...your_gemini_api_key_here

# PostgreSQL Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rag_haui
DB_USER=postgres
DB_PASSWORD=mat_khau_postgres_cua_ban

# Cau hinh LLM Provider: "ollama" (Local GPU) hoac "gemini" (Cloud)
LLM_PROVIDER=ollama
LOCAL_LLM_MODEL=qwen3.5:4b:rag
OLLAMA_BASE_URL=http://localhost:11434

# Thiet lap toi uu VRAM cho GPU 4GB (RTX 3050 Laptop)
OLLAMA_NUM_CTX=3072
OLLAMA_NUM_PREDICT=1024
OLLAMA_NUM_GPU=999

# Model Gemini Cloud (dung khi LLM_PROVIDER=gemini hoac fallback)
LLM_MODEL=gemini-3.6-flash
FALLBACK_LLM_MODEL=gemini-3.1-flash-lite

# Backend Server
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
```

---

## 5. Huong Dan Khoi Chay Nhanh (Dung 3 File .bat)

Thu tu thuc hien chuan xac tren may moi:

### Buoc 1: Chay `setup.bat`
- Nhap dup chuot vao file `setup.bat` tai thu muc goc.
- Script se tu dong:
  1. Kiem tra phien ban Python trong PATH.
  2. Tao moi truong ao `venv`.
  3. Nang cap pip va cai dat tat ca thu vien tu `requirements.txt`.
  4. Kiem tra su ton tai cua file `.env`.
  5. Kiem tra ket noi den PostgreSQL va dem so ban ghi trong bang `documents`.

### Buoc 2: Chinh sua file `.env`
- Neu buoc 1 bao chua co file `.env` hoac ket noi DB chua thanh cong, hay mo file `.env` va cap nhat `GEMINI_API_KEY` va `DB_PASSWORD` nhu huong dan o Muc 4.

### Buoc 3: Chay `setup_model.bat` (Neu dung Ollama)
- Dam bao da cai dat Ollama tren may.
- Nhap dup chuot vao file `setup_model.bat`.
- Menu lua chon mo hinh se xuat hien:
  - Phim 1: **Qwen 3.5 4B** (Khuyen dung nhat: Tieng Viet xuat sac, toi uu VRAM 3.1 - 3.3 GB).
  - Phim 2: **Qwen 2.5 3B** (On dinh, VRAM ~2.3 GB).
  - Phim 3: **Gemma 3 4B** (Google, VRAM ~3.2 GB).
  - Phim 4: **Gemma 2 2B** (Sieu nhe, VRAM ~1.8 GB).
- Script se tu dong pull model tu Ollama, tao custom Modelfile voi prompt system nghiem ngat, toi uu hoa bo dem VRAM va tu dong ghi ten model vao file `.env`.

### Buoc 4: Chay `run.bat`
- Nhap dup chuot vao file `run.bat`.
- Menu khoi dong xuat hien:
  - **Nhap 1 (Mac dinh):** Khoi chay toan bo he thong.
    - Cua so 1: Live Log Monitor (Giam sat hoat dong va loi he thong thoi gian thuc).
    - Cua so 2: Backend FastAPI Server (http://127.0.0.1:8000).
    - Cua so 3: Frontend Streamlit Web App (http://localhost:8501).
  - **Nhap 2:** Tro chuyen truc tiep qua Terminal CLI.
  - **Nhap 3:** Chi chay Frontend Streamlit.
  - **Nhap 4:** Chi chay Backend FastAPI.
  - **Nhap 5:** Mo cong cu cau hinh/doi model Ollama.
  - **Nhap 6:** Chay bo kiem thu tu dong (Pytest).

---

## 6. Huong Dan Khoi Chay Thu Cong (Manual Command Line)

Neu khong dung file `.bat`, co the khoi chay he thong thong qua terminal PowerShell hoac CMD:

```bash
# 1. Kich hoat moi truong ao
.\venv\Scripts\activate

# 2. Thiet lap PYTHONPATH (neu can)
$env:PYTHONPATH = "src;."

# 3. Khoi chay Backend FastAPI (Terminal 1)
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# 4. Khoi chay Frontend Streamlit (Terminal 2)
streamlit run frontend/app.py

# 5. Khoi chay Terminal Chat CLI (Neu muon chat console)
python terminal_chat.py
```

- **Swagger API Documentation:** http://127.0.0.1:8000/docs
- **Giao dien Chat Streamlit:** http://localhost:8501

---

## 7. Cau Truc Thu Muc Du An

Du an to chuc theo Clean Architecture:

```text
haui_rag/
|-- backend/                       # Tang giao tiep REST API (FastAPI)
|   |-- api/                       # Router cho chat, conversations, feedback
|   |-- schemas/                   # Pydantic request/response models
|   `-- main.py                    # Entrypoint server, CORS, Lifespan migration
|-- frontend/                      # Giao dien nguoi dung (Streamlit)
|   |-- components/                # UI components: chat, sidebar, metadata viewer
|   |-- styles/                    # Tinh chinh CSS tuy bien
|   `-- app.py                     # Entrypoint frontend
|-- src/haui_rag/                  # Core Business Domain (Logic loi)
|   |-- core/                      # RAG Orchestrator, Embedding, Retrieval, Generation
|   |-- db/                        # Ket noi Postgres, pgvector queries, Migrator
|   |-- prompts/                   # System prompt template phong ngua ao giac
|   |-- utils/                     # Sanitizer chong prompt injection, che PII
|   |-- config.py                  # Doc va xac thuc bien moi truong
|   `-- logger.py                  # Cau hinh logging xoay vong file
|-- migrations/                    # Tap tin SQL migration cho cac bang ung dung
|-- scripts/                       # Tap hop cac script tien ich, benchmark, giam sat
|   |-- monitor_logs.py            # Cua so giam sat live log
|   `-- run_evaluation.py          # Script danh gia 30 cau hoi vang
|-- tests/                         # Bo kiem thu tu dong (unit, integration, e2e)
|-- data/                          # Du lieu luu tru, logs, ket qua danh gia
|-- .env.example                   # File mau cau hinh bien moi truong
|-- requirements.txt               # Danh sach dependencies
|-- setup.bat                      # Script thiet lap moi truong tu dong
|-- setup_model.bat                # Script tai va cau hinh Local LLM
`-- run.bat                        # Trinh quan ly khoi dong ung dung Master Runner
```

---

## 8. Xu Ly Su Co Thuong Gap (Troubleshooting)

### 8.1. Loi `type "vector" does not exist`
- **Nguyen nhan:** PostgreSQL chua duoc cai extension pgvector hoac chua kich hoat tren database `rag_haui`.
- **Khac phuc:** Mo `psql`, ket noi vao `rag_haui` va chay lenh `CREATE EXTENSION vector;`. Neu PostgreSQL bao loi khong tim thay file extension, can tai va cai dat bo cai pgvector cho ban PostgreSQL tuong ung tren Windows.

### 8.2. Loi khong ket noi duoc Database (Connection refused / Password authentication failed)
- **Nguyen nhan:** PostgreSQL service chua chay hoac sai mat khau trong `.env`.
- **Khac phuc:**
  - Kiem tra dich vu PostgreSQL trong `services.msc` da chuyen sang `Running`.
  - Kiem tra `DB_USER` va `DB_PASSWORD` trong file `.env` da dung voi tai khoan postgres tren may chua.

### 8.3. Loi `GEMINI_API_KEY` hoac loi 429 Quota Exceeded
- **Nguyen nhan:** Chua dien API key hop le hoac tai khoan Google bi het han muc free tier.
- **Khac phuc:** Kiem tra lai API key tren Google AI Studio. Neu can su dung du phong, chuyen sang dung key khac hoac giam bot so request gui lien tuc.

### 8.4. Ollama bao loi `connection refused` tai port 11434
- **Nguyen nhan:** Ung dung Ollama chua duoc khoi dong ngam.
- **Khac phuc:** Mo Start Menu go `Ollama` de ung dung chay duoi khay he thong (System Tray), hoac mo terminal go lenh `ollama serve`.

### 8.5. Xung dot cong 8000 hoac 8501
- **Nguyen nhan:** Tien trinh chay truoc do chua tat hoac co phan mem khac chiem cong.
- **Khac phuc:** Mo Task Manager tat cac tien trinh `python.exe` chay ngam hoac kiem tra bang lenh:
  ```powershell
  netstat -ano | findstr :8000
  netstat -ano | findstr :8501
  ```
  Sau do dung `taskkill /PID <so_pid> /F` de giai phong cong.

---

## 9. Kiem Thu He Thong

Kiem tra toan bo tinh nang he thong thong qua Pytest:

```bash
.\venv\Scripts\activate
pytest tests/ -v
```

De danh gia chat luong phan hoi RAG voi bo 30 cau hoi vang:

```bash
python scripts/run_evaluation.py
```

Ket qua bao cao se duoc xuat chi tiet tai `data/test_data/evaluation_report.json`.
