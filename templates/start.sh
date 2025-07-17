#!/usr/bin/env bash

# Install Playwright browsers if not already installed
python -m playwright install

# Start FastAPI app
gunicorn main:app --bind 0.0.0.0:$PORT --worker-class uvicorn.workers.UvicornWorker
