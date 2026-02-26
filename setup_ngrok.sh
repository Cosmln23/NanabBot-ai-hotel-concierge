#!/bin/bash
# Script for ngrok setup - exposes localhost to the internet

echo "=========================================="
echo "NGROK SETUP - Expose WhatsApp Webhook"
echo "=========================================="

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo ""
    echo "❌ ngrok is not installed!"
    echo ""
    echo "📥 Install ngrok:"
    echo "   1. MacOS: brew install ngrok"
    echo "   2. Or download from: https://ngrok.com/download"
    echo ""
    exit 1
fi

echo ""
echo "✅ ngrok is installed"
echo ""
echo "🚀 Starting ngrok tunnel on port 8000..."
echo ""
echo "IMPORTANT:"
echo "  - Keep this terminal open!"
echo "  - Copy the HTTPS URL below"
echo "  - Append at the end: /webhook/whatsapp"
echo ""
echo "Example:"
echo "  If you see: https://abc123.ngrok.io"
echo "  Use: https://abc123.ngrok.io/webhook/whatsapp"
echo ""
echo "=========================================="
echo ""

# Start ngrok
ngrok http 8000
