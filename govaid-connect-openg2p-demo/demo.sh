#!/bin/bash

set -e

ENV_FILE=".env"
COOKIE_FILE="cookies-wso2.txt"
TOKEN_FILE=".token"

echo "===================================================="
echo "🚀 GovAid OpenG2P + WSO2 End-to-End Demo"
echo "===================================================="

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ .env file not found"
  echo "Create .env with WSO2_TOKEN_URL, WSO2_GATEWAY_URL, CONSUMER_KEY, CONSUMER_SECRET, ODOO_DB, ODOO_LOGIN, ODOO_PASSWORD"
  exit 1
fi

source "$ENV_FILE"

if [ -z "$CONSUMER_KEY" ] || [ -z "$CONSUMER_SECRET" ]; then
  echo "❌ CONSUMER_KEY or CONSUMER_SECRET is missing in .env"
  exit 1
fi

echo ""
echo "1️⃣ Checking Docker containers..."
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "govaid-openg2p|govaid-wso2am|govaid-postgres" || {
  echo "❌ Required GovAid containers are not running"
  echo "Run: docker compose up -d"
  exit 1
}

echo ""
echo "2️⃣ Generating WSO2 OAuth2 access token..."

TOKEN_RESPONSE=$(curl -sk -X POST "$WSO2_TOKEN_URL" \
  -u "$CONSUMER_KEY:$CONSUMER_SECRET" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials")

TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    token = data.get('access_token')
    if not token:
        print('')
    else:
        print(token)
except Exception:
    print('')
")

if [ -z "$TOKEN" ]; then
  echo "❌ Failed to generate WSO2 access token"
  echo "Response:"
  echo "$TOKEN_RESPONSE"
  exit 1
fi

echo "$TOKEN" > "$TOKEN_FILE"
echo "✅ Token generated. Length: ${#TOKEN}"

echo ""
echo "3️⃣ Logging into Odoo/OpenG2P through WSO2..."

LOGIN_RESPONSE=$(curl -sk -i -c "$COOKIE_FILE" -X POST \
  "$WSO2_GATEWAY_URL/web/session/authenticate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"jsonrpc\": \"2.0\",
    \"params\": {
      \"db\": \"$ODOO_DB\",
      \"login\": \"$ODOO_LOGIN\",
      \"password\": \"$ODOO_PASSWORD\"
    }
  }")

echo "$LOGIN_RESPONSE" > /tmp/govaid_login_response.txt

if echo "$LOGIN_RESPONSE" | grep -q "\"uid\""; then
  echo "✅ Odoo/OpenG2P login through WSO2 successful"
else
  echo "❌ Odoo/OpenG2P login failed"
  echo "$LOGIN_RESPONSE"
  exit 1
fi

TIMESTAMP=$(date +%Y%m%d%H%M%S)

BENEFICIARY_NAME="WSO2 Beneficiary Demo $TIMESTAMP"
BENEFICIARY_EMAIL="wso2.beneficiary.$TIMESTAMP@example.com"
HOUSEHOLD_NAME="WSO2 Household Demo $TIMESTAMP"

echo ""
echo "4️⃣ Creating Individual Beneficiary through WSO2..."
echo "Beneficiary Name: $BENEFICIARY_NAME"

BENEFICIARY_RESPONSE=$(curl -sk -X POST \
  "$WSO2_GATEWAY_URL/web/dataset/call_kw/res.partner/create" \
  -b "$COOKIE_FILE" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"jsonrpc\": \"2.0\",
    \"params\": {
      \"model\": \"res.partner\",
      \"method\": \"create\",
      \"args\": [{
        \"name\": \"$BENEFICIARY_NAME\",
        \"family_name\": \"WSO2\",
        \"given_name\": \"Beneficiary\",
        \"email\": \"$BENEFICIARY_EMAIL\",
        \"phone\": \"0771112222\",
        \"is_registrant\": true,
        \"is_group\": false,
        \"income\": 35000
      }],
      \"kwargs\": {}
    }
  }")

echo "$BENEFICIARY_RESPONSE" > /tmp/govaid_beneficiary_response.json

BENEFICIARY_ID=$(echo "$BENEFICIARY_RESPONSE" | python3 -c "
import sys, json
try:
    data=json.load(sys.stdin)
    print(data.get('result', ''))
except Exception:
    print('')
")

if [ -z "$BENEFICIARY_ID" ] || [ "$BENEFICIARY_ID" = "False" ]; then
  echo "❌ Failed to create beneficiary"
  echo "$BENEFICIARY_RESPONSE"
  exit 1
fi

echo "✅ Beneficiary created. ID: $BENEFICIARY_ID"

echo ""
echo "5️⃣ Creating Household / Group through WSO2..."
echo "Household Name: $HOUSEHOLD_NAME"

GROUP_RESPONSE=$(curl -sk -X POST \
  "$WSO2_GATEWAY_URL/web/dataset/call_kw/res.partner/create" \
  -b "$COOKIE_FILE" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"jsonrpc\": \"2.0\",
    \"params\": {
      \"model\": \"res.partner\",
      \"method\": \"create\",
      \"args\": [{
        \"name\": \"$HOUSEHOLD_NAME\",
        \"is_registrant\": true,
        \"is_group\": true
      }],
      \"kwargs\": {}
    }
  }")

echo "$GROUP_RESPONSE" > /tmp/govaid_group_response.json

GROUP_ID=$(echo "$GROUP_RESPONSE" | python3 -c "
import sys, json
try:
    data=json.load(sys.stdin)
    print(data.get('result', ''))
except Exception:
    print('')
")

if [ -z "$GROUP_ID" ] || [ "$GROUP_ID" = "False" ]; then
  echo "❌ Failed to create household/group"
  echo "$GROUP_RESPONSE"
  exit 1
fi

echo "✅ Household/Group created. ID: $GROUP_ID"

echo ""
echo "6️⃣ Creating Membership through WSO2..."
echo "Linking Individual $BENEFICIARY_ID to Group $GROUP_ID"

MEMBERSHIP_RESPONSE=$(curl -sk -X POST \
  "$WSO2_GATEWAY_URL/web/dataset/call_kw/g2p.group.membership/create" \
  -b "$COOKIE_FILE" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"jsonrpc\": \"2.0\",
    \"params\": {
      \"model\": \"g2p.group.membership\",
      \"method\": \"create\",
      \"args\": [{
        \"group\": $GROUP_ID,
        \"individual\": $BENEFICIARY_ID
      }],
      \"kwargs\": {}
    }
  }")

echo "$MEMBERSHIP_RESPONSE" > /tmp/govaid_membership_response.json

MEMBERSHIP_ID=$(echo "$MEMBERSHIP_RESPONSE" | python3 -c "
import sys, json
try:
    data=json.load(sys.stdin)
    print(data.get('result', ''))
except Exception:
    print('')
")

if [ -z "$MEMBERSHIP_ID" ] || [ "$MEMBERSHIP_ID" = "False" ]; then
  echo "❌ Failed to create membership"
  echo "$MEMBERSHIP_RESPONSE"
  exit 1
fi

echo "✅ Membership created. ID: $MEMBERSHIP_ID"

echo ""
echo "7️⃣ Verifying Beneficiary through WSO2..."

VERIFY_BENEFICIARY=$(curl -sk -X POST \
  "$WSO2_GATEWAY_URL/web/dataset/call_kw/res.partner/search_read" \
  -b "$COOKIE_FILE" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"jsonrpc\": \"2.0\",
    \"params\": {
      \"model\": \"res.partner\",
      \"method\": \"search_read\",
      \"args\": [[[\"id\", \"=\", $BENEFICIARY_ID]]],
      \"kwargs\": {
        \"fields\": [\"id\", \"name\", \"email\", \"phone\", \"is_group\", \"is_registrant\", \"income\"],
        \"limit\": 1
      }
    }
  }")

echo "$VERIFY_BENEFICIARY" | python3 -m json.tool || echo "$VERIFY_BENEFICIARY"

echo ""
echo "8️⃣ Verifying Membership through WSO2..."

VERIFY_MEMBERSHIP=$(curl -sk -X POST \
  "$WSO2_GATEWAY_URL/web/dataset/call_kw/g2p.group.membership/search_read" \
  -b "$COOKIE_FILE" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"jsonrpc\": \"2.0\",
    \"params\": {
      \"model\": \"g2p.group.membership\",
      \"method\": \"search_read\",
      \"args\": [[[\"group\", \"=\", $GROUP_ID]]],
      \"kwargs\": {
        \"fields\": [\"id\", \"group\", \"individual\", \"status\", \"start_date\"],
        \"limit\": 10
      }
    }
  }")

echo "$VERIFY_MEMBERSHIP" | python3 -m json.tool || echo "$VERIFY_MEMBERSHIP"

echo ""
echo "===================================================="
echo "✅ GovAid End-to-End Demo Completed Successfully"
echo "===================================================="
echo "WSO2 Gateway URL:      $WSO2_GATEWAY_URL"
echo "Beneficiary ID:        $BENEFICIARY_ID"
echo "Beneficiary Name:      $BENEFICIARY_NAME"
echo "Household/Group ID:    $GROUP_ID"
echo "Household/Group Name:  $HOUSEHOLD_NAME"
echo "Membership ID:         $MEMBERSHIP_ID"
echo ""
echo "Now verify in Odoo UI:"
echo "http://localhost:8069"
echo ""
echo "Go to:"
echo "Registry → Individuals → search: $BENEFICIARY_NAME"
echo "Registry → Groups → search: $HOUSEHOLD_NAME"
echo "===================================================="