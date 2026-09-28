@echo off
title haui_rag Runner

echo =====================================================================
echo   TRO LY AI TRA CUU QUY CHE HAUI (haui_rag)
echo =====================================================================
echo.

set "PYTHONPATH=%~dp0src;%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo [LOI] Chua tim thay moi truong ao venv!
    echo Vui long chay file setup.bat truoc.
    echo.
    pause
    exit /b 1
)

echo [CHON CHE DO KHOI DONG]:
echo   1. Khoi chay ca Backend API va Frontend UI (Khuyen nghi)
echo   2. Chi chay Giao dien Chat Streamlit
echo   3. Chi chay FastAPI Backend Server (Port 8000)
echo   4. Chay kiem thu he thong (Pytest)
echo.
set "choice=1"
set /p choice="Nhap lua chon [1-4] (mac dinh 1): "
if defined choice set choice=%choice: =%

if "%choice%"=="1" goto opt_all
if "%choice%"=="2" goto opt_frontend
if "%choice%"=="3" goto opt_backend
if "%choice%"=="4" goto opt_test
goto opt_all

:opt_all
echo.
echo [1/2] Dang khoi dong Backend API tai http://127.0.0.1:8000 ...
start "haui_rag Backend (FastAPI)" cmd /k "cd /d %~dp0 && call venv\Scripts\activate.bat && uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"
ping 127.0.0.1 -n 3 >nul
echo [2/2] Dang khoi dong Giao dien Streamlit tai http://localhost:8501 ...
start "haui_rag Frontend (Streamlit)" cmd /k "cd /d %~dp0 && call venv\Scripts\activate.bat && streamlit run frontend/app.py"
echo.
echo =====================================================================
echo   HE THONG DA KHOI CHAY THANH CONG!
echo   - Backend API Docs : http://127.0.0.1:8000/docs
echo   - Giao dien Chat   : http://localhost:8501
echo =====================================================================
ping 127.0.0.1 -n 4 >nul
exit /b 0

:opt_frontend
echo.
echo Dang mo giao dien Streamlit...
call venv\Scripts\activate.bat
streamlit run frontend/app.py
exit /b 0

:opt_backend
echo.
echo Dang mo FastAPI server...
call venv\Scripts\activate.bat
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
exit /b 0

:opt_test
echo.
echo Dang chay kiem thu...
call venv\Scripts\activate.bat
pytest tests/
echo.
pause
exit /b 0
