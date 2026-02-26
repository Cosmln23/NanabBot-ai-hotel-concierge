#!/bin/bash
# AI Hotel Suite Daily Health Check Script
# Run on server: bash /root/app/scripts/daily-check.sh

echo "================================================"
echo "  AI Hotel Suite Daily Health Check"
echo "  $(date '+%Y-%m-%d %H:%M:%S UTC')"
echo "================================================"
echo ""

PASS="✅"
WARN="⚠️"
FAIL="❌"

# 1. DISK
DISK_PCT=$(df / --output=pcent | tail -1 | tr -d ' %')
DISK_USED=$(df -h / --output=used | tail -1 | tr -d ' ')
DISK_TOTAL=$(df -h / --output=size | tail -1 | tr -d ' ')
if [ "$DISK_PCT" -lt 70 ]; then
    echo "$PASS Disk: ${DISK_PCT}% used (${DISK_USED}/${DISK_TOTAL})"
elif [ "$DISK_PCT" -lt 85 ]; then
    echo "$WARN Disk: ${DISK_PCT}% used (${DISK_USED}/${DISK_TOTAL}) - Clean up docker!"
else
    echo "$FAIL Disk: ${DISK_PCT}% used (${DISK_USED}/${DISK_TOTAL}) - URGENT: free up space!"
fi

# 2. MEMORY
MEM_PCT=$(free | awk '/Mem:/ {printf "%.0f", $3/$2*100}')
if [ "$MEM_PCT" -lt 80 ]; then
    echo "$PASS Memory: ${MEM_PCT}% used"
elif [ "$MEM_PCT" -lt 90 ]; then
    echo "$WARN Memory: ${MEM_PCT}% used - needs monitoring!"
else
    echo "$FAIL Memory: ${MEM_PCT}% used - CRITICAL!"
fi

# 3. SWAP
SWAP_TOTAL=$(free | awk '/Swap:/ {print $2}')
if [ "$SWAP_TOTAL" -gt 0 ]; then
    SWAP_PCT=$(free | awk '/Swap:/ {printf "%.0f", $3/$2*100}')
else
    SWAP_PCT=0
fi
if [ "$SWAP_PCT" -lt 20 ]; then
    echo "$PASS Swap: ${SWAP_PCT}% used"
elif [ "$SWAP_PCT" -lt 50 ]; then
    echo "$WARN Swap: ${SWAP_PCT}% used"
else
    echo "$FAIL Swap: ${SWAP_PCT}% used - MEMORY ISSUE!"
fi

# 4. DOCKER CONTAINERS
echo ""
RUNNING=$(docker ps --format '{{.Names}}' 2>/dev/null | wc -l)
EXPECTED=4
if [ "$RUNNING" -eq "$EXPECTED" ]; then
    echo "$PASS Docker: ${RUNNING}/${EXPECTED} containers running"
else
    echo "$FAIL Docker: ${RUNNING}/${EXPECTED} containers running - PLEASE CHECK!"
    docker ps -a --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null
fi

# 5. DOCKER ERRORS (last hour)
WEB_ERRORS=$(docker compose logs --since=1h web 2>&1 | grep -v "attribute.*version.*obsolete" | grep -ci "error\|traceback\|exception") || WEB_ERRORS=0
WORKER_ERRORS=$(docker compose logs --since=1h worker 2>&1 | grep -v "attribute.*version.*obsolete" | grep -v "retrying in.*seconds" | grep -ci "error\|traceback\|exception") || WORKER_ERRORS=0
if [ "$WEB_ERRORS" -eq 0 ] 2>/dev/null && [ "$WORKER_ERRORS" -eq 0 ] 2>/dev/null; then
    echo "$PASS Logs last hour: 0 errors"
else
    echo "$WARN Logs last hour: web=${WEB_ERRORS} errors, worker=${WORKER_ERRORS} errors"
fi

# 6. WEBHOOK (last hour)
WEBHOOKS=$(docker compose logs --since=1h web 2>/dev/null | grep -c "POST /webhook/whatsapp" || echo 0)
echo "$PASS WhatsApp Webhooks (last hour): ${WEBHOOKS} requests"

# 7. SITE ONLINE
echo ""
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 https://yourdomain.com/ 2>/dev/null)
if [ "$HTTP_CODE" = "200" ]; then
    echo "$PASS Site: yourdomain.com is responding (HTTP ${HTTP_CODE})"
else
    echo "$FAIL Site: yourdomain.com NOT responding (HTTP ${HTTP_CODE}) - URGENT!"
fi

# 8. SSL CERTIFICATE
SSL_EXPIRY=$(echo | openssl s_client -connect yourdomain.com:443 -servername yourdomain.com 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
if [ -n "$SSL_EXPIRY" ]; then
    SSL_EPOCH=$(date -d "$SSL_EXPIRY" +%s 2>/dev/null)
    NOW_EPOCH=$(date +%s)
    DAYS_LEFT=$(( (SSL_EPOCH - NOW_EPOCH) / 86400 ))
    if [ "$DAYS_LEFT" -gt 30 ]; then
        echo "$PASS SSL: expires in ${DAYS_LEFT} days (${SSL_EXPIRY})"
    elif [ "$DAYS_LEFT" -gt 7 ]; then
        echo "$WARN SSL: expires in ${DAYS_LEFT} days - check auto-renew!"
    else
        echo "$FAIL SSL: expires in ${DAYS_LEFT} days - URGENT RENEWAL NEEDED!"
    fi
else
    echo "$WARN SSL: could not verify expiration"
fi

# 9. META WHATSAPP API
echo ""
if [ -f /root/app/.env ]; then
    WA_TOKEN=$(grep "^WHATSAPP_ACCESS_TOKEN=" /root/app/.env | cut -d= -f2)
    WA_PHONE_ID=$(grep "^WHATSAPP_PHONE_NUMBER_ID=" /root/app/.env | cut -d= -f2)

    if [ -n "$WA_TOKEN" ] && [ -n "$WA_PHONE_ID" ]; then
        META_RESPONSE=$(curl -s --max-time 10 "https://graph.facebook.com/v21.0/${WA_PHONE_ID}?fields=quality_rating,name_status,account_mode&access_token=${WA_TOKEN}" 2>/dev/null)

        QUALITY=$(echo "$META_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('quality_rating','UNKNOWN'))" 2>/dev/null)
        NAME_STATUS=$(echo "$META_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('name_status','UNKNOWN'))" 2>/dev/null)
        ACC_MODE=$(echo "$META_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('account_mode','UNKNOWN'))" 2>/dev/null)

        if [ "$QUALITY" = "GREEN" ]; then
            echo "$PASS WhatsApp Quality: ${QUALITY}"
        elif [ "$QUALITY" = "YELLOW" ]; then
            echo "$WARN WhatsApp Quality: ${QUALITY} - Watch quality!"
        else
            echo "$FAIL WhatsApp Quality: ${QUALITY} - ISSUE REPORTED!"
        fi

        if [ "$NAME_STATUS" = "APPROVED" ]; then
            echo "$PASS WhatsApp Name: ${NAME_STATUS}"
        else
            echo "$WARN WhatsApp Name: ${NAME_STATUS}"
        fi

        if [ "$ACC_MODE" = "LIVE" ]; then
            echo "$PASS WhatsApp Mode: ${ACC_MODE}"
        else
            echo "$FAIL WhatsApp Mode: ${ACC_MODE} - Not LIVE!"
        fi
    else
        echo "$WARN WhatsApp: Missing Token or Phone ID from .env"
    fi
else
    echo "$WARN .env file not found"
fi

# 10. OPENAI API
OPENAI_KEY=$(grep "^OPENAI_API_KEY=" /root/app/.env 2>/dev/null | cut -d= -f2)
if [ -n "$OPENAI_KEY" ]; then
    OAI_RESPONSE=$(curl -s --max-time 10 -o /dev/null -w "%{http_code}" "https://api.openai.com/v1/models" -H "Authorization: Bearer ${OPENAI_KEY}" 2>/dev/null)
    if [ "$OAI_RESPONSE" = "200" ]; then
        echo "$PASS OpenAI API: Key is valid (HTTP ${OAI_RESPONSE})"
    else
        echo "$FAIL OpenAI API: Issue detected (HTTP ${OAI_RESPONSE}) - Check credits/key!"
    fi
fi

# 11. REDIS
REDIS_PING=$(docker compose exec -T redis redis-cli ping 2>/dev/null | tr -d '\r')
if [ "$REDIS_PING" = "PONG" ]; then
    echo "$PASS Redis: PONG - working"
else
    echo "$FAIL Redis: Not responding - ISSUE REPORTED!"
fi

# 12. UBUNTU UPDATES
echo ""
UPDATES=$(apt list --upgradable 2>/dev/null | grep -c "upgradable" || echo "0")
UPDATES=$(echo "$UPDATES" | tr -d '[:space:]')
if [ "$UPDATES" -eq 0 ] 2>/dev/null; then
    echo "$PASS Ubuntu: Up to date, 0 updates available"
elif [ "$UPDATES" -lt 30 ] 2>/dev/null; then
    echo "$WARN Ubuntu: ${UPDATES} updates available"
else
    echo "$FAIL Ubuntu: ${UPDATES} updates - Please update system!"
fi

# RESTART REQUIRED?
if [ -f /var/run/reboot-required ]; then
    echo "$WARN Ubuntu: SERVER RESTART REQUIRED"
fi

# UPTIME
UPTIME=$(uptime -p)
echo "   Server uptime: $UPTIME"

echo ""
echo "================================================"
echo "  Check completed! $(date '+%H:%M:%S')"
echo "================================================"
