#!/bin/bash

# Install Playwright browsers
echo "Installing Playwright browsers..."
playwright install --with-deps

# Start the FastAPI app using uvicorn
echo "Starting the FastAPI server..."
uvicorn main:app --host 0.0.0.0 --port 10000
