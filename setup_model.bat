@echo off
setlocal enabledelayedexpansion
chcp 65001 > nul

REM ---------------------------------------------------------------------------
REM HaUI RAG Assistant - Script thiet lap mo hinh Local LLM (Ollama)
REM Ho tro: Gemma 3 4B, Gemma 2 2B, Qwen 2.5 3B, Llama 3.2 3B hoac model tuy chon
REM Tu dong tinh chinh VRAM 3.0 - 3.5 GB cho GPU RTX 3050 Laptop (4GB VRAM)
REM ---------------------------------------------------------------------------

echo [THONG TIN] Khoi tao chuong trinh cau hinh mo hinh Local LLM cho haui_rag...
echo.

REM 1. Kiem tra Ollama da duoc cai dat hay chua
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo [LOI] Chua tim thay Ollama trong PATH he thong!
    echo Vui long tai va cai dat Ollama tai: https://ollama.com/download
    echo Sau khi cai dat xong, hay chay lai file setup_model.bat nay.
    pause
    exit /b 1
)

REM 2. Kiem tra dich vu Ollama dang chay chua, neu chua thi khoi dong
curl.exe -s http://localhost:11434/api/tags >nul 2>nul
if %errorlevel% neq 0 (
    echo [THONG TIN] Dich vu Ollama chua chay. Dang khoi dong Ollama serve ngam...
    start /b "" ollama serve >nul 2>nul
    timeout /t 3 /nobreak >nul
)

REM 3. Chon mo hinh muon su dung
set "SELECTED_BASE_MODEL="
set "CUSTOM_VRAM_CTX=3072"
set "MODEL_DISPLAY_NAME="

if not "%~1"=="" (
    set "SELECTED_BASE_MODEL=%~1"
    set "MODEL_DISPLAY_NAME=%~1"
    goto :APPLY_MODEL
)

echo ---------------------------------------------------------------------------
echo Chon mo hinh LLM ban muon trien khai:
echo [1] Qwen 3.5 4B (Alibaba - Khuyen dung nhat: Tieng Viet xuat sac, VRAM ~3.1-3.3 GB)
echo [2] Qwen 2.5 3B (Alibaba - VRAM ~2.3 GB, ngon ngu tu nhien, cuc ky on dinh)
echo [3] Gemma 3 4B  (Google - VRAM ~3.1-3.3 GB, suy luan va RAG chat che)
echo [4] Gemma 2 2B  (Google - Sieu nhe: VRAM ~1.8 GB, phan hoi cuc nhanh)
echo [5] Llama 3.2 3B (Meta - VRAM ~2.2 GB, toi uu cho RAG bien canh)
echo [6] Nhap ten model Ollama tuy chon khac
echo ---------------------------------------------------------------------------
set /p "CHOICE=Nhap lua chon cua ban (1-6, mac dinh 1): "

if "%CHOICE%"=="2" (
    set "SELECTED_BASE_MODEL=qwen2.5:3b"
    set "MODEL_DISPLAY_NAME=Qwen 2.5 (3B)"
    set "CUSTOM_VRAM_CTX=3072"
) else if "%CHOICE%"=="3" (
    set "SELECTED_BASE_MODEL=gemma3:4b"
    set "MODEL_DISPLAY_NAME=Gemma 3 (4B)"
    set "CUSTOM_VRAM_CTX=3072"
) else if "%CHOICE%"=="4" (
    set "SELECTED_BASE_MODEL=gemma2:2b"
    set "MODEL_DISPLAY_NAME=Gemma 2 (2B)"
    set "CUSTOM_VRAM_CTX=3072"
) else if "%CHOICE%"=="5" (
    set "SELECTED_BASE_MODEL=llama3.2:3b"
    set "MODEL_DISPLAY_NAME=Llama 3.2 (3B)"
    set "CUSTOM_VRAM_CTX=3072"
) else if "%CHOICE%"=="6" (
    set /p "CUSTOM_MODEL_INPUT=Nhap ten model tren Ollama (vi du deepseek-r1:1.5b): "
    if "!CUSTOM_MODEL_INPUT!"=="" (
        echo [LOI] Ten model khong duoc de trong.
        pause
        exit /b 1
    )
    set "SELECTED_BASE_MODEL=!CUSTOM_MODEL_INPUT!"
    set "MODEL_DISPLAY_NAME=!CUSTOM_MODEL_INPUT!"
    set "CUSTOM_VRAM_CTX=3072"
) else (
    set "SELECTED_BASE_MODEL=qwen3.5:4b"
    set "MODEL_DISPLAY_NAME=Qwen 3.5 (4B)"
    set "CUSTOM_VRAM_CTX=3072"
)

:APPLY_MODEL
echo.
echo [THONG TIN] Mo hinh da chon: !MODEL_DISPLAY_NAME! (!SELECTED_BASE_MODEL!)
echo [THONG TIN] Cau hinh gioi han VRAM: num_ctx = !CUSTOM_VRAM_CTX! (dam bao muc 3.0 - 3.5 GB VRAM)
echo.

REM 4. Tai mo hinh goc qua Ollama
echo [1/4] Dang tai mo hinh !SELECTED_BASE_MODEL! tu Ollama Library...
ollama pull !SELECTED_BASE_MODEL!
if %errorlevel% neq 0 (
    echo [LOI] Khong the tai mo hinh !SELECTED_BASE_MODEL!. Vui long kiem tra ket noi mang.
    pause
    exit /b 1
)

REM 5. Tao file Modelfile dong cho mo hinh RAG
set "RAG_MODEL_NAME=!SELECTED_BASE_MODEL!:rag"
set "TEMP_MODELFILE=%~dp0scripts\Modelfile.active"

echo [2/4] Dang tao tap tin cau hinh VRAM cho mo hinh !RAG_MODEL_NAME!...
(
    echo FROM !SELECTED_BASE_MODEL!
    echo.
    echo # Cau hinh gioi han VRAM 3.0 - 3.5 GB tren GPU RTX 3050 Laptop
    echo PARAMETER num_ctx !CUSTOM_VRAM_CTX!
    echo PARAMETER num_predict 1024
    echo PARAMETER temperature 0.1
    echo PARAMETER top_p 0.95
    echo PARAMETER repeat_penalty 1.1
    echo.
    echo SYSTEM """Ban la Tro ly AI tra cuu van ban, quy che va quy dinh cua Truong Dai hoc Cong nghiep Ha Noi (HaUI). Chi su dung thong tin trong ngu canh duoc cung cap de tra loi. Khong bia dat thong tin."""
) > "%TEMP_MODELFILE%"

echo [3/4] Dang dong goi mo hinh !RAG_MODEL_NAME! voi Ollama...
ollama create !RAG_MODEL_NAME! -f "%TEMP_MODELFILE%"
if %errorlevel% neq 0 (
    echo [CANH BAO] Khong tao duoc model custom, he thong se su dung truc tiep !SELECTED_BASE_MODEL!
    set "FINAL_MODEL=!SELECTED_BASE_MODEL!"
) else (
    set "FINAL_MODEL=!RAG_MODEL_NAME!"
)

REM 6. Cap nhat file .env
echo [4/4] Dang cap nhat cau hinh vao file .env...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$envFile = '%~dp0.env';" ^
    "if (Test-Path $envFile) {" ^
    "    $content = Get-Content $envFile -Raw -Encoding UTF8;" ^
    "    if ($content -match 'LOCAL_LLM_MODEL=.*') {" ^
    "        $content = $content -replace 'LOCAL_LLM_MODEL=.*', 'LOCAL_LLM_MODEL=!FINAL_MODEL!';" ^
    "    } else {" ^
    "        $content += [Environment]::NewLine + 'LOCAL_LLM_MODEL=!FINAL_MODEL!';" ^
    "    }" ^
    "    if ($content -match 'LLM_PROVIDER=.*') {" ^
    "        $content = $content -replace 'LLM_PROVIDER=.*', 'LLM_PROVIDER=ollama';" ^
    "    } else {" ^
    "        $content += [Environment]::NewLine + 'LLM_PROVIDER=ollama';" ^
    "    }" ^
    "    if ($content -match 'OLLAMA_NUM_CTX=.*') {" ^
    "        $content = $content -replace 'OLLAMA_NUM_CTX=.*', 'OLLAMA_NUM_CTX=!CUSTOM_VRAM_CTX!';" ^
    "    } else {" ^
    "        $content += [Environment]::NewLine + 'OLLAMA_NUM_CTX=!CUSTOM_VRAM_CTX!';" ^
    "    }" ^
    "    Set-Content -Path $envFile -Value $content -Encoding UTF8 -NoNewline;" ^
    "    Write-Host 'Da cap nhat .env thanh cong voi LOCAL_LLM_MODEL=!FINAL_MODEL!';" ^
    "} else {" ^
    "    Write-Warning 'Khong tim thay file .env de cap nhat';" ^
    "}"

echo.
echo ---------------------------------------------------------------------------
echo [THANH CONG] Thiet lap mo hinh hoan tat!
echo Mo hinh dang hoat dong: !FINAL_MODEL!
echo Provider: ollama (Local GPU RTX 3050, VRAM: 3.0 - 3.5 GB)
echo ---------------------------------------------------------------------------
echo.
echo Ban co the khoi dong he thong bang cac lenh:
echo   - Backend API:  .\venv\Scripts\python -m uvicorn backend.main:app --port 8000
echo   - Frontend UI:  .\venv\Scripts\streamlit run frontend\app.py
echo.
pause
