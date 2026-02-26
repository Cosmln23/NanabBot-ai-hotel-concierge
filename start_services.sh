#!/bin/bash
# Stop existing services
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "rq worker" 2>/dev/null
sleep 2

# Fix macOS fork() crash with RQ worker
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# Set correct WhatsApp token (overrides any shell environment)
export WHATSAPP_ACCESS_TOKEN='your_token_here'

# Start services
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/uvicorn.log 2>&1 &
nohup .venv/bin/rq worker --with-scheduler > /tmp/rq_worker.log 2>&1 &

echo "✅ Services started with new WhatsApp token"
sleep 2
ps aux | grep -E "uvicorn|rq worker" | grep -v grep
