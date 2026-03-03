#!/bin/bash

# Create necessary directories
mkdir -p audio_downloads logs

# Initialize database
python init_db.py

# Start the application with gunicorn
gunicorn run:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120