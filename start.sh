#!/bin/bash
echo "Installing Playwright browsers..."
python -m playwright install chromium --with-deps

echo "Starting FastAPI with Uvicorn..."
uvicorn main:app --host 0.0.0.0 --port 10000
