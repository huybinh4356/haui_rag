@echo off
chcp 65001 > nul
title haui_rag Master Runner

echo ---------------------------------------------------------------------
echo   TRO LY AI TRA CUU QUY CHE HAUI (haui_rag)
echo ---------------------------------------------------------------------
echo.

set "PYTHONPATH=%~dp0src;%~dp0"

if not exist "%~dp0venv\Scripts\activate.bat" (
    echo [LOI] Chua tim thay moi truong ao venv!
    echo Vui long chay file setup.bat truoc.
    echo.
    pause
    exit /b 1
)

echo [CHON CHE DO KHOI DONG]:
echo   1. Khoi chay ca Web App (kem Cua so Giam sat Log song song)
echo   2. Tro chuyen Terminal (kem Cua so Giam sat Log song song)
echo   3. Chi chay Giao dien Chat Streamlit (Port 8501)
echo   4. Chi chay FastAPI Backend Server (Port 8000)
echo   5. Cau hinh / Doi mo hinh Local LLM (Qwen, Gemma, Llama)
echo   6. Chay kiem thu toan bo he thong (Pytest)
echo   7. Chi mo Cua so Giam sat Log & Loi he thong (Log Monitor)
echo.
set "choice=1"
set /p choice="Nhap lua chon [1-7] (mac dinh 1): "
if defined choice set choice=%choice: =%

if "%choice%"=="1" goto opt_all
if "%choice%"=="2" goto opt_terminal
if "%choice%"=="3" goto opt_frontend
if "%choice%"=="4" goto opt_backend
if "%choice%"=="5" goto opt_model
if "%choice%"=="6" goto opt_test
if "%choice%"=="7" goto opt_monitor
goto opt_all

:opt_all
echo.
echo [1/3] Dang mo Cua so Giam sat Log (Live Log Monitor)...
start "haui_rag Log Monitor" cmd /k "cd /d %~dp0 && call venv\Scripts\activate.bat && python scripts\monitor_logs.py"
echo [2/3] Dang khoi dong Backend API tai http://127.0.0.1:8000 ...
start "haui_rag Backend (FastAPI)" cmd /k "cd /d %~dp0 && call venv\Scripts\activate.bat && uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"
ping 127.0.0.1 -n 3 >nul
echo [3/3] Dang khoi dong Giao dien Streamlit tai http://localhost:8501 ...
start "haui_rag Frontend (Streamlit)" cmd /k "cd /d %~dp0 && call venv\Scripts\activate.bat && streamlit run frontend/app.py"
echo.
echo ---------------------------------------------------------------------
echo   HE THONG DA KHOI CHAY THANH CONG!
echo   - Backend API Docs : http://127.0.0.1:8000/docs
echo   - Giao dien Chat   : http://localhost:8501
echo   - Giam sat Logs    : Da mo cua so Live Log Monitor song song
echo ---------------------------------------------------------------------
ping 127.0.0.1 -n 4 >nul
exit /b 0

:opt_terminal
echo.
echo [1/2] Dang mo Cua so Giam sat Log (Live Log Monitor) song song...
start "haui_rag Log Monitor" cmd /k "cd /d %~dp0 && call venv\Scripts\activate.bat && python scripts\monitor_logs.py"
echo [2/2] Dang khoi chay Terminal Chat...
call "%~dp0venv\Scripts\activate.bat"
python "%~dp0terminal_chat.py"
echo.
pause
exit /b 0

:opt_frontend
echo.
echo Dang mo giao dien Streamlit...
call "%~dp0venv\Scripts\activate.bat"
streamlit run frontend/app.py
exit /b 0

:opt_backend
echo.
echo Dang mo FastAPI server...
call "%~dp0venv\Scripts\activate.bat"
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
exit /b 0

:opt_model
echo.
echo Dang mo cong cu cau hinh mo hinh Local LLM...
call "%~dp0setup_model.bat"
exit /b 0

:opt_test
echo.
echo Dang chay kiem thu toan bo he thong...
call "%~dp0venv\Scripts\activate.bat"
pytest tests/ -v
echo.
pause
exit /b 0

:opt_monitor
echo.
echo Dang mo Cua so Giam sat Log...
call "%~dp0venv\Scripts\activate.bat"
python "%~dp0scripts\monitor_logs.py"
exit /b 0
