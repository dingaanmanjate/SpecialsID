import os
import json
import boto3
from PIL import Image
import io

# S3 Configuration from environment variables
S3_BUCKET = os.environ.get("S3_BUCKET_NAME")
IMAGE_PREFIX = "data/interim/images/PnP/"
OUTPUT_PREFIX = "data/shr/products/PnP/"

PADDING_PERCENT = 0.10  # 10% padding for better leverage/framing
s3_client = boto3.client('s3')

def upload_to_s3(image_bytes, s3_key):
    if not S3_BUCKET:
        print(f"S3_BUCKET_NAME not set, skipping upload")
        return
    try:
        s3_client.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=image_bytes, ContentType='image/jpeg')
    except Exception as e:
        print(f"Failed to upload to S3: {e}")

def process_json(json_key):
    # json_key example: data/pro/json/PnP/Gauteng/Weekly_Specials/page_1.json
    try:
        relative_path_part = json_key.split('data/pro/json/PnP/')[1]
        relative_no_ext = os.path.splitext(relative_path_part)[0]
    except IndexError:
        print(f"Invalid JSON key structure: {json_key}")
        return

    # Corresponding Image Key: data/interim/images/PnP/Gauteng/Weekly_Specials/page_1.jpg
    image_key = f"{IMAGE_PREFIX}{relative_no_ext}.jpg"
    
    print(f"Reading JSON from S3: {json_key}")
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=json_key)
        products = json.loads(response['Body'].read())
    except Exception as e:
        print(f"Error reading JSON from S3: {e}")
        return

    if not products:
        print("No products found in JSON.")
        return

    print(f"Reading image from S3: {image_key}")
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=image_key)
        image_bytes = response['Body'].read()
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
    except Exception as e:
        print(f"Error reading image from S3: {e}")
        return

    print(f"✂️ Cropping {len(products)} products...")

    for i, product in enumerate(products):
        bbox = product.get("bounding_box")
        if not bbox or len(bbox) != 4:
            continue

        # Bounding box is [ymin, xmin, ymax, xmax] normalized 0-1000
        ymin, xmin, ymax, xmax = bbox
        
        # Calculate original dimensions
        box_width = xmax - xmin
        box_height = ymax - ymin
        
        # Apply padding
        xmin_pad = max(0, xmin - (box_width * PADDING_PERCENT))
        ymin_pad = max(0, ymin - (box_height * PADDING_PERCENT))
        xmax_pad = min(1000, xmax + (box_width * PADDING_PERCENT))
        ymax_pad = min(1000, ymax + (box_height * PADDING_PERCENT))

        # Convert normalized to pixel coordinates
        left = (xmin_pad / 1000) * width
        top = (ymin_pad / 1000) * height
        right = (xmax_pad / 1000) * width
        bottom = (ymax_pad / 1000) * height

        try:
            cropped_img = img.crop((left, top, right, bottom))
            
            # Sanitize product name for filename
            raw_name = product.get("product_name", f"product_{i}")
            prod_name = "".join([c if c.isalnum() or c in " _-" else "_" for c in raw_name])
            prod_name = prod_name.replace(" ", "_").strip("_")[:50]
            
            crop_filename = f"{i}_{prod_name}.jpg"
            # Output key: data/shr/products/PnP/Gauteng/Weekly_Specials/page_1/0_product_name.jpg
            s3_output_key = f"{OUTPUT_PREFIX}{relative_no_ext}/{crop_filename}"
            
            img_byte_arr = io.BytesIO()
            cropped_img.save(img_byte_arr, format='JPEG', quality=90)
            upload_to_s3(img_byte_arr.getvalue(), s3_output_key)
            
        except Exception as e:
            print(f"❌ Failed to crop product {i}: {e}")

def lambda_handler(event, context):
    """
    Triggered by S3 ObjectCreated events for JSON files.
    """
    for record in event.get('Records', []):
        key = record['s3']['object']['key']
        
        if key.endswith('.json') and 'data/pro/json/PnP/' in key:
            print(f"Processing new JSON: {key}")
            process_json(key)
            
    return {
        'statusCode': 200,
        'body': json.dumps('Cropping complete')
    }
