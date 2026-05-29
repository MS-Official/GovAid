# Now every time your token expires, just run:
# ./scripts/govaid-login.sh

#!/bin/bash

set -e

ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ .env file not found"
  exit 1
fi

source "$ENV_FILE"

echo "🔐 Generating WSO2 access token..."

TOKEN_RESPONSE=$(curl -sk -X POST "$WSO2_TOKEN_URL" \
  -u "$CONSUMER_KEY:$CONSUMER_SECRET" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials")

TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "
import sys, json
data=json.load(sys.stdin)
if 'access_token' not in data:
    print('ERROR')
    sys.exit(1)
print(data['access_token'])
")

if [ "$TOKEN" = "ERROR" ] || [ -z "$TOKEN" ]; then
  echo "❌ Failed to generate token"
  echo "$TOKEN_RESPONSE"
  exit 1
fi

echo "✅ Token generated. Length: ${#TOKEN}"

echo "🔑 Logging into Odoo through WSO2..."

curl -sk -i -c cookies-wso2.txt -X POST \
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
  }" > /tmp/govaid-login-response.txt

if grep -q "\"uid\"" /tmp/govaid-login-response.txt; then
  echo "✅ Odoo login through WSO2 successful"
else
  echo "❌ Odoo login failed"
  cat /tmp/govaid-login-response.txt
  exit 1
fi

echo "$TOKEN" > .token

echo "✅ Saved:"
echo "   Token: .token"
echo "   Cookie: cookies-wso2.txt"

echo ""
echo "To use the token manually, run:"
echo "export TOKEN=\$(cat .token)"