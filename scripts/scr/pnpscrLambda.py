import os
import json
import requests
import boto3
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from botocore.exceptions import ClientError

# Configuration for AWS Lambda
# Lambda only has write access to /tmp
BASE_URL = "https://www.pnp.co.za/catalogues"
ROOT_DIR = "/tmp/data/raw/PnP"
USER_DATA_DIR = "/tmp/user_data"

# S3 Configuration from environment variables
S3_BUCKET = os.environ.get("S3_BUCKET_NAME")
S3_PREFIX = "data/raw/PnP/"

s3_client = boto3.client('s3')

def file_exists_in_s3(s3_key):
    if not S3_BUCKET:
        return False
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        raise

def upload_to_s3(local_path, s3_key):
    if not S3_BUCKET:
        print(f"S3_BUCKET_NAME not set, skipping upload of {local_path}")
        return
    try:
        s3_client.upload_file(local_path, S3_BUCKET, s3_key)
        print(f"Successfully uploaded {local_path} to s3://{S3_BUCKET}/{s3_key}")
    except Exception as e:
        print(f"Failed to upload to S3: {e}")

def download_catalogues():
    # Ensure directories exist in /tmp
    os.makedirs(ROOT_DIR, exist_ok=True)
    os.makedirs(USER_DATA_DIR, exist_ok=True)

    with sync_playwright() as p:
        # Note: Standard playwright might not work in Lambda without specific layers/binaries.
        # This setup assumes the environment is configured with necessary dependencies.
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR, 
            headless=True, 
            args=[
                "--disable-blink-features=AutomationControlled",
                "--excludeSwitches=enable-automation",
                "--use-mock-keychain",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process"
            ]
        ) 
        
        page = context.new_page()
        Stealth().apply_stealth_sync(page)
        
        print(f"Opening {BASE_URL}...")
        try:
            page.goto(BASE_URL, wait_until="networkidle", timeout=60000)
        except Exception as e:
            print(f"Initial load timed out, attempting to proceed... {e}")

        try:
            page.wait_for_selector(".pdfdownload", timeout=20000)
        except Exception:
            print("Standard selector failed. Attempting to find regional text as fallback...")
            try:
                page.wait_for_selector("text=Gauteng", timeout=15000)
            except Exception:
                print("Failed to find download elements.")
                context.close()
                return

        download_containers = page.query_selector_all("div.pdfdownload")
        print(f"Found {len(download_containers)} download containers.")

        url_to_path = {}
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        })

        for container in download_containers:
            parent = container.evaluate_handle("el => el.closest('.content')")
            date_element = parent.query_selector(".cat-validity-date")
            date_text = date_element.inner_text().strip() if date_element else "unknown_date"
            
            clean_date_text = date_text.replace("Valid", "").strip()
            date_slug = "".join([c if c.isalnum() or c in ("_", "-") else "_" for c in clean_date_text])

            links = container.query_selector_all("a")
            for link in links:
                province = link.inner_text().strip().replace(" ", "_")
                href = link.get_attribute("href")
                
                if not href or ".pdf" not in href.lower() or "Shop_now" in province:
                    continue

                s3_key = f"{S3_PREFIX}{province}/{date_slug}.pdf"
                target_dir = os.path.join(ROOT_DIR, province)
                os.makedirs(target_dir, exist_ok=True)
                file_path = os.path.join(target_dir, f"{date_slug}.pdf")

                if file_exists_in_s3(s3_key):
                    print(f"Skipping {province} ({date_text}) - already exists in S3.")
                    continue

                if os.path.exists(file_path):
                    print(f"Skipping {province} ({date_text}) - already exists locally.")
                    upload_to_s3(file_path, s3_key)
                    continue

                if href in url_to_path:
                    print(f"Linking {province} to already downloaded file for {href}")
                    with open(url_to_path[href], 'rb') as f_src:
                        with open(file_path, 'wb') as f_dst:
                            f_dst.write(f_src.read())
                    upload_to_s3(file_path, s3_key)
                    continue

                try:
                    print(f"Downloading {province} ({date_text}) from {href}...")
                    response = session.get(href, timeout=30)
                    response.raise_for_status()
                    
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                    
                    url_to_path[href] = file_path
                    print(f"Successfully saved to {file_path}")
                    upload_to_s3(file_path, s3_key)
                except Exception as e:
                    print(f"Failed to download {province}: {e}")

        context.close()

def lambda_handler(event, context):
    try:
        download_catalogues()
        return {
            'statusCode': 200,
            'body': json.dumps('Catalogues downloaded successfully')
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error downloading catalogues: {str(e)}")
        }

if __name__ == "__main__":
    download_catalogues()
