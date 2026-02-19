import os
import json
import boto3
import time
from google import genai
from google.genai import types
from PIL import Image
import io

# S3 Configuration from environment variables
S3_BUCKET = os.environ.get("S3_BUCKET_NAME")
OUTPUT_PREFIX = "data/pro/json/PnP/"
GEMINI_API_KEY_SSM_NAME = os.environ.get("GEMINI_API_KEY_SSM_NAME", "/SpecialsID/gemini_api_key")

MODELS = ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-3-flash-preview"]
s3_client = boto3.client('s3')
ssm_client = boto3.client('ssm')
lambda_client = boto3.client('lambda')

def file_exists_in_s3(bucket, key):
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except:
        return False

# Global client to be initialized lazily
_genai_clients = []
_current_client_index = 0

def get_genai_clients():
    global _genai_clients
    if not _genai_clients:
        print(f"Fetching API keys from SSM: {GEMINI_API_KEY_SSM_NAME}")
        try:
            response = ssm_client.get_parameter(
                Name=GEMINI_API_KEY_SSM_NAME,
                WithDecryption=True
            )
            # Support multiple keys separated by commas
            api_keys = [k.strip() for k in response['Parameter']['Value'].split(',') if k.strip()]
            
            for key in api_keys:
                _genai_clients.append(genai.Client(api_key=key))
                
            if not _genai_clients:
                raise Exception("No Gemini API keys found in SSM parameter.")
            print(f"Successfully loaded {len(_genai_clients)} API keys.")
        except Exception as e:
            print(f"Error fetching API keys: {e}")
            raise
            
    return _genai_clients

def get_current_client():
    clients = get_genai_clients()
    return clients[_current_client_index]

def rotate_client():
    global _current_client_index
    clients = get_genai_clients()
    _current_client_index = (_current_client_index + 1) % len(clients)
    print(f"🔄 Rotating to Gemini API key index: {_current_client_index}")
    return clients[_current_client_index]

SYSTEM_INSTRUCTION = """
You are a specialized grocery data extractor for the South African market.
Analyze the provided flyer image and extract products into a JSON array.
Include:
- product_name: Full name (e.g., 'Clover Cheese Assorted')
- brand: (e.g., 'Clover')
- current_price: Float value (e.g., 160.00)
- was_price: Float or null
- weight_volume: Numeric part only (e.g., 550)
- unit: (e.g., 'g', 'kg', 'l', 'pack')
- deal_type: Identify SA promos ('Any 2', 'Combo', 'Smart Shopper', 'Bulk')
- multi_buy_quantity: Number of items for the price (default 1)
- bounding_box: [ymin, xmin, ymax, xmax] normalized 0-1000

Note: If a deal says 'All 3 for R75', extract each item separately and link them with a shared 'group_id'.
"""

def upload_to_s3(data, s3_key):
    if not S3_BUCKET:
        print(f"S3_BUCKET_NAME not set, skipping upload")
        return
    try:
        s3_client.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=json.dumps(data, indent=4))
        print(f"Successfully uploaded JSON to s3://{S3_BUCKET}/{s3_key}")
    except Exception as e:
        print(f"Failed to upload to S3: {e}")

def process_image(s3_key):
    # s3_key example: data/interim/images/PnP/Gauteng/Weekly_Specials/page_1.jpg
    filename = os.path.basename(s3_key)
    
    # Extract relative path to reconstruct output structure
    try:
        relative_path = s3_key.split('data/interim/images/PnP/')[1]
        output_key = f"{OUTPUT_PREFIX}{os.path.splitext(relative_path)[0]}.json"
    except IndexError:
        output_key = f"{OUTPUT_PREFIX}{os.path.splitext(filename)[0]}.json"

    if file_exists_in_s3(S3_BUCKET, output_key):
        print(f"⏩ Skipping (already exists in S3): {output_key}")
        return "skipped"

    print(f"Downloading image from S3: {s3_key}")
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        image_bytes = response['Body'].read()
        img = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        print(f"Error reading image from S3: {e}")
        return "error"

    # Try models
    for model_id in MODELS:
        clients = get_genai_clients()
        # Try each client for the current model if rate limited
        for _ in range(len(clients)):
            client = get_current_client()
            try:
                print(f"🔍 Processing with model: {model_id} (Key Index: {_current_client_index})")
                response = client.models.generate_content(
                    model=model_id,
                    contents=[img, "Extract grocery data according to system instructions."],
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        response_mime_type="application/json"
                    )
                )

                data = response.parsed if hasattr(response, 'parsed') and response.parsed is not None else None
                
                if data is None and hasattr(response, 'text') and response.text:
                    try:
                        data = json.loads(response.text)
                    except json.JSONDecodeError:
                        pass

                if data:
                    upload_to_s3(data, output_key)
                    print(f"✅ Success with {model_id}")
                    return "processed"
                else:
                    print(f"⚠️ No data extracted with {model_id}")
                    break # Move to next model if no data but no error

            except Exception as e:
                error_msg = str(e).lower()
                print(f"❌ Error with {model_id} (Key Index: {_current_client_index}): {e}")
                if "429" in error_msg or "resource_exhausted" in error_msg:
                    if len(clients) > 1:
                        print(f"Rate limit hit, rotating client...")
                        rotate_client()
                        continue # Retry same model with next client
                    else:
                        print(f"Rate limit hit and only one key available.")
                        break # Move to next model
                break # Non-rate-limit error, move to next model

    print(f"❌ All models and keys failed for {s3_key}")
    return "failed"

def discover_and_process(prefix, token, context):
    """
    Lists all images in a prefix and processes them recursively.
    """
    print(f"🕵️ Starting discovery in: {prefix}")
    params = {'Bucket': S3_BUCKET, 'Prefix': prefix}
    if token:
        params['ContinuationToken'] = token

    response = s3_client.list_objects_v2(**params)
    
    if 'Contents' not in response:
        print("No more files to process.")
        return

    for obj in response['Contents']:
        # Check remaining time (stop if less than 60 seconds remain)
        if context.get_remaining_time_in_millis() < 60000:
            print("⏳ Time running out. Triggering next batch...")
            new_token = response.get('NextContinuationToken') or response.get('ContinuationToken')
            if not new_token: # list_objects_v2 might not give NextContinuationToken if it's the last page
                # If we don't have a token but we have more pages, we might need to handle this.
                # However, list_objects_v2 with pagination is usually better.
                pass
            
            trigger_self(prefix, response.get('NextContinuationToken'))
            return

        key = obj['Key']
        if (key.endswith('.jpg') or key.endswith('.png')) and 'data/interim/images/PnP/' in key:
            print(f"Processing image from discovery: {key}")
            result = process_image(key)
            if result == "processed":
                time.sleep(2) # Small delay to respect quotas

    # If there are more pages, trigger the next one
    if response.get('IsTruncated'):
        print("Moving to next page of S3 results...")
        trigger_self(prefix, response.get('NextContinuationToken'))

def trigger_self(prefix, token):
    """
    Invokes the current lambda function asynchronously.
    """
    payload = {
        'discovery_prefix': prefix,
        'continuation_token': token
    }
    print(f"Self-triggering with token: {token}")
    lambda_client.invoke(
        FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME'),
        InvocationType='Event',
        Payload=json.dumps(payload)
    )

def lambda_handler(event, context):
    """
    Handles both S3 events and recursive discovery events.
    """
    # 1. Check for Discovery/Crawl mode
    if 'discovery_prefix' in event:
        discover_and_process(event['discovery_prefix'], event.get('continuation_token'), context)
        return {'statusCode': 200, 'body': 'Discovery initiated'}

    # 2. Check for S3 Events
    for record in event.get('Records', []):
        key = record['s3']['object']['key']
        if (key.endswith('.jpg') or key.endswith('.png')) and 'data/interim/images/PnP/' in key:
            print(f"Processing new image: {key}")
            process_image(key)
            
    return {
        'statusCode': 200,
        'body': json.dumps('Vision parsing complete')
    }
