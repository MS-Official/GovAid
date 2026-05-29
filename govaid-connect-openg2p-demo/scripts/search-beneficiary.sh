#!/bin/bash

set -e

source .env

TOKEN=$(cat .token)

echo "🔎 Searching beneficiary through WSO2..."

curl -sk -X POST \
  "$WSO2_GATEWAY_URL/web/dataset/call_kw/res.partner/search_read" \
  -b cookies-wso2.txt \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "params": {
      "model": "res.partner",
      "method": "search_read",
      "args": [[["name", "ilike", "WSO2 Beneficiary Demo"]]],
      "kwargs": {
        "fields": ["id", "name", "email", "phone", "is_group", "is_registrant", "income"],
        "limit": 10
      }
    }
  }'

echo ""