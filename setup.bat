@echo off
chcp 65001 >nul

echo =====================================================================
echo   TRỢ LÝ AI TRA CỨU QUY CHẾ HAUI (haui_rag) - SETUP
echo =====================================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [LOI] Khong tim thay Python trong PATH. Vui long cai dat Python 3.11.
    pause
    exit /b 1
)

echo [1/4] Kiem tra moi truong venv...
if not exist "venv\Scripts\activate.bat" (
    echo       Dang tao venv...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [LOI] Khong the tao venv!
        pause
        exit /b 1
    )
    echo       Da tao venv thanh cong!
) else (
    echo       Moi truong venv da san sang.
)

echo.
echo [2/4] Cai dat dependencies tu requirements.txt...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [LOI] Cai dat dependencies that bai!
    pause
    exit /b 1
)
echo       Cai dat dependencies thanh cong!

echo.
echo [3/4] Kiem tra file .env...
if not exist ".env" (
    echo [CANH BAO] Chua co file .env! Dang tao file mau...
    (
        echo GEMINI_API_KEY=your_key_here
        echo DB_HOST=localhost
        echo DB_PORT=5432
        echo DB_NAME=rag_haui
        echo DB_USER=postgres
        echo DB_PASSWORD=your_password
    ) > .env
    echo Vui long cap nhat API key va mat khau DB vao file .env!
) else (
    echo       File .env da ton tai.
)

echo.
echo [4/4] Kiem tra he thong va ket noi PostgreSQL...
python -c "from haui_rag.config import validate_config; validate_config(); from haui_rag.db import connect_db; conn = connect_db(); cur = conn.cursor(); cur.execute('SELECT COUNT(*) FROM documents;'); print('      [OK] So luong chunks trong DB:', cur.fetchone()[0]); conn.close()" 2>nul
if %errorlevel% neq 0 (
    echo [LUU Y] Chua ket noi duoc Database hoac GEMINI_API_KEY chua dung.
) else (
    echo       Ket noi PostgreSQL va Vector Database hoan hao!
)

echo.
echo =====================================================================
echo   SETUP HOAN TAT! Ban co the chay file run.bat de bat dau.
echo =====================================================================
echo.
pause
