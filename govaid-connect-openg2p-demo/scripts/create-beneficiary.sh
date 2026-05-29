#!/bin/bash

set -e

source .env

if [ ! -f ".token" ]; then
  echo "❌ Token not found. Run ./scripts/govaid-login.sh first"
  exit 1
fi

if [ ! -f "cookies-wso2.txt" ]; then
  echo "❌ Odoo cookie not found. Run ./scripts/govaid-login.sh first"
  exit 1
fi

TOKEN=$(cat .token)

echo "👤 Creating beneficiary through WSO2..."

curl -sk -X POST \
  "$WSO2_GATEWAY_URL/web/dataset/call_kw/res.partner/create" \
  -b cookies-wso2.txt \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "params": {
      "model": "res.partner",
      "method": "create",
      "args": [{
        "name": "WSO2 Beneficiary Demo",
        "family_name": "WSO2",
        "given_name": "Beneficiary",
        "email": "wso2.beneficiary@example.com",
        "phone": "0771112222",
        "is_registrant": true,
        "is_group": false,
        "income": 35000
      }],
      "kwargs": {}
    }
  }'

echo ""
echo "✅ Beneficiary create request completed"