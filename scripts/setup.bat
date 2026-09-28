@echo off
cd /d "%~dp0\.."
echo Dang tao moi truong ao...
python -m venv venv
call venv\Scripts\activate
pip install -r requirements.txt
echo Xong!
