#!/bin/bash

# Install required Python packages
pip install -r requirements.txt

# Install Playwright browsers (headless Chromium)
playwright install --with-deps

# Start the server
uvicorn main:app --host 0.0.0.0 --port 10000
