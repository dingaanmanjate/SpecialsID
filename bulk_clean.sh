#!/bin/bash

# Configuration
BUCKET="special-id-data-0129"
PREFIX="data/pro/json/PnP/"
LAMBDA_NAME="specials-id-data-cleaner"
TMP_DIR="/tmp/bulk_clean_outputs"
PROFILE="capaciti"

# Create temp directory for response payloads
mkdir -p "$TMP_DIR"

echo "🔍 Fetching JSON files from s3://$BUCKET/$PREFIX..."

# Get all JSON keys, handling pagination automatically
KEYS=$(aws-vault exec "$PROFILE" -- aws s3api list-objects-v2 --bucket "$BUCKET" --prefix "$PREFIX" --query "Contents[?ends_with(Key, '.json')].Key" --output text | tr '	' '\n')

if [ -z "$KEYS" ]; then
    echo "❌ No JSON files found in s3://$BUCKET/$PREFIX"
    exit 1
fi

COUNT=$(echo "$KEYS" | wc -l)
echo "🚀 Found $COUNT files. Starting bulk clean..."

SUCCESS_COUNT=0
FAILURE_COUNT=0

for KEY in $KEYS; do
    echo -n "  -> Processing: $KEY ... "
    
    # Strip the .json extension and replace slashes for a cleaner filename
    BASE_NAME=$(echo "$KEY" | sed 's/\.json$//' | tr '/' '_')
    RESPONSE_FILE="$TMP_DIR/${BASE_NAME}.json"
    ERR_FILE="$TMP_DIR/${BASE_NAME}.err"
    
    # Construct the S3 event payload
    PAYLOAD=$(cat <<EOF
{
  "Records": [
    {
      "s3": {
        "bucket": { "name": "$BUCKET" },
        "object": { "key": "$KEY" }
      }
    }
  ]
}
EOF
)

    # Invoke Lambda synchronously to catch execution errors
    # Note: AWS CLI v1 does not support --cli-binary-format
    aws-vault exec "$PROFILE" -- aws lambda invoke \
        --function-name "$LAMBDA_NAME" \
        --payload "$PAYLOAD" \
        --invocation-type RequestResponse \
        "$RESPONSE_FILE" 2>"$ERR_FILE" > /dev/null

    # Check if the AWS CLI command succeeded
    if [ $? -eq 0 ]; then
        # Check the actual Lambda response for errors
        if grep -q "FunctionError" "$RESPONSE_FILE" 2>/dev/null || grep -q "errorMessage" "$RESPONSE_FILE" 2>/dev/null; then
            echo "❌ FAILED (Lambda Error)"
            cat "$RESPONSE_FILE"
            ((FAILURE_COUNT++))
        else
            echo "✅ SUCCESS"
            ((SUCCESS_COUNT++))
        fi
    else
        echo "❌ FAILED (CLI/Network Error)"
        cat "$ERR_FILE"
        ((FAILURE_COUNT++))
    fi
done

echo "----------------------------------------------------"
echo "✨ Bulk Clean Complete!"
echo "✅ Successful: $SUCCESS_COUNT"
echo "❌ Failed:     $FAILURE_COUNT"
echo "📂 Individual logs saved in: $TMP_DIR"
echo "----------------------------------------------------"
