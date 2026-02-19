import os
import json
import boto3
from pathlib import Path
from pdf2image import convert_from_path
from botocore.exceptions import ClientError

# S3 Configuration from environment variables
S3_BUCKET = os.environ.get("S3_BUCKET_NAME")
# Input: data/raw/PnP/Province/Flyer.pdf
# Output: data/interim/images/PnP/Province/Flyer/page_1.jpg

s3_client = boto3.client('s3')

def upload_to_s3(local_path, s3_key):
    if not S3_BUCKET:
        print(f"S3_BUCKET_NAME not set, skipping upload of {local_path}")
        return
    try:
        s3_client.upload_file(local_path, S3_BUCKET, s3_key)
        print(f"Successfully uploaded {local_path} to s3://{S3_BUCKET}/{s3_key}")
    except Exception as e:
        print(f"Failed to upload to S3: {e}")

def process_pdf(s3_key):
    # s3_key example: data/raw/PnP/Gauteng/Weekly_Specials.pdf
    filename = os.path.basename(s3_key)
    flyer_name = os.path.splitext(filename)[0]
    
    # Extract province from key structure: data/raw/PnP/{province}/{filename}
    parts = s3_key.split('/')
    if len(parts) >= 4:
        province = parts[3]
    else:
        province = "unknown"

    local_pdf_path = f"/tmp/{filename}"
    output_base_dir = f"/tmp/images/{province}/{flyer_name}"
    os.makedirs(output_base_dir, exist_ok=True)

    print(f"Downloading {s3_key} from {S3_BUCKET}...")
    try:
        s3_client.download_file(S3_BUCKET, s3_key, local_pdf_path)
    except Exception as e:
        print(f"Error downloading from S3: {e}")
        return

    try:
        # Convert PDF to High-Res JPEG (300 DPI for AI clarity)
        # Note: poppler must be in the PATH (e.g., via Lambda Layer)
        images = convert_from_path(local_pdf_path, dpi=300)
        
        for i, image in enumerate(images):
            image_filename = f"page_{i + 1}.jpg"
            local_image_path = os.path.join(output_base_dir, image_filename)
            image.save(local_image_path, "JPEG")
            
            # S3 Output Key: data/interim/images/PnP/{province}/{flyer_name}/page_{i+1}.jpg
            s3_output_key = f"data/interim/images/PnP/{province}/{flyer_name}/{image_filename}"
            upload_to_s3(local_image_path, s3_output_key)
            
            # Clean up local image
            os.remove(local_image_path)
            
    except Exception as e:
        print(f"Error converting {filename}: {e}")
    finally:
        if os.path.exists(local_pdf_path):
            os.remove(local_pdf_path)

def lambda_handler(event, context):
    """
    Triggered by S3 ObjectCreated events.
    """
    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        # Only process PDFs in the raw directory
        if key.endswith('.pdf') and 'data/raw/PnP/' in key:
            print(f"Processing new PDF: {key}")
            process_pdf(key)
            
    return {
        'statusCode': 200,
        'body': json.dumps('PDF processing complete')
    }
