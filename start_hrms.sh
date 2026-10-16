#!/bin/bash
# Smart HRMS Auto-start Script
# Add this to your shell profile (~/.bashrc, ~/.zshrc) or create a systemd user service

PROJECT_DIR="/home/raj/smart-hrms"
VENV_DIR="$PROJECT_DIR/venv"

start_hrms() {
    cd "$PROJECT_DIR"
    source "$VENV_DIR/bin/activate"
    python manage.py runserver 0.0.0.0:8000
}

# If run directly, start the server
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    start_hrms
fi