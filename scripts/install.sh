#!/bin/bash
set -e

echo "⚙ Installing JARVIS..."

# Python venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt --only-binary=numpy,sounddevice

# Playwright browsers
playwright install chromium

# React dashboard
cd ui/dashboard
npm install
npm run build
cd ../..

# Config
cp .env.example .env

echo "✅ JARVIS installed successfully."
echo "👉 Edit .env and add your ANTHROPIC_API_KEY"
echo "👉 Then run: python main.py"
