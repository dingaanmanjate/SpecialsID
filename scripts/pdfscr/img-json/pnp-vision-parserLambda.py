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

MODELS = ["gemini-2.0-flash-lite", "gemini-1.5-flash", "gemini-2.0-flash"]
s3_client = boto3.client('s3')
ssm_client = boto3.client('ssm')

# Global client to be initialized lazily
_genai_client = None

def get_genai_client():
    global _genai_client
    if _genai_client is None:
        print(f"Fetching API key from SSM: {GEMINI_API_KEY_SSM_NAME}")
        response = ssm_client.get_parameter(
            Name=GEMINI_API_KEY_SSM_NAME,
            WithDecryption=True
        )
        api_key = response['Parameter']['Value']
        # Initialize GenAI Client with the key from SSM
        _genai_client = genai.Client(api_key=api_key)
    return _genai_client

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

    print(f"Downloading image from S3: {s3_key}")
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        image_bytes = response['Body'].read()
        img = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        print(f"Error reading image from S3: {e}")
        return

    client = get_genai_client()

    # Try models
    for model_id in MODELS:
        try:
            print(f"🔍 Processing with model: {model_id}")
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
                return
            else:
                print(f"⚠️ No data extracted with {model_id}")

        except Exception as e:
            print(f"❌ Error with {model_id}: {e}")
            if "429" in str(e) or "resource_exhausted" in str(e).lower():
                print("Rate limit hit, moving to next model...")
                continue
            continue

    print(f"❌ All models failed for {s3_key}")

def lambda_handler(event, context):
    """
    Triggered by S3 ObjectCreated events.
    """
    for record in event.get('Records', []):
        key = record['s3']['object']['key']
        
        # Only process images in the interim directory
        if (key.endswith('.jpg') or key.endswith('.png')) and 'data/interim/images/PnP/' in key:
            print(f"Processing new image: {key}")
            process_image(key)
            
    return {
        'statusCode': 200,
        'body': json.dumps('Vision parsing complete')
    }
