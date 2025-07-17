#!/bin/bash

# Set the path for Playwright to install its browsers
export PLAYWRIGHT_BROWSERS_PATH=/mnt/cache/.playwright

echo "Installing Playwright browsers..."
python -m playwright install chromium --with-deps

echo "Starting FastAPI with Uvicorn..."
uvicorn main:app --host 0.0.0.0 --port 10000
