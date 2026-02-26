#!/bin/bash
# RQ Worker startup script with macOS fork() fix

# Fix for macOS objc threading issue with fork()
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# Activate virtual environment
source venv/bin/activate

# Start RQ worker
exec rq worker --url redis://localhost:6379/0
