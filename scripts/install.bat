@echo off
echo Installing JARVIS...

python -m venv .venv
call .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt --only-binary=numpy,sounddevice
playwright install chromium

cd ui\dashboard
npm install
npm run build
cd ..\..

copy .env.example .env

echo.
echo JARVIS installed successfully.
echo Edit .env and add your ANTHROPIC_API_KEY
echo Then run: python main.py
