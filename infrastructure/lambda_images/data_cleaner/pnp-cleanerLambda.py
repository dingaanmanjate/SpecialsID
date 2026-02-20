import os
import json
import boto3
import awswrangler as wr
import pandas as pd
import re

# S3 Configuration from environment variables
S3_BUCKET = os.environ.get("S3_BUCKET_NAME")
OUTPUT_PREFIX = "data/clean/PnP/"

s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')

def normalize_brand(brand):
    if not brand:
        return None
    brand = str(brand).strip()
    # Common normalization
    mapping = {
        "Pick n Pay": "PnP",
        "no name™": "no name",
        "no name": "no name",
        "KOO": "Koo",
    }
    return mapping.get(brand, brand)

def normalize_unit(unit):
    if not unit:
        return None
    unit = str(unit).lower().strip()
    # Common normalization
    mapping = {
        "l": "litre",
        "litre": "litre",
        "litres": "litre",
        "l": "litre",
        "ml": "ml",
        "g": "g",
        "kg": "kg",
        "pack": "pack",
        "each": "each",
    }
    # Handle cases like "8kg" or "500g" in unit
    if re.match(r"^\d+(kg|g|ml|l)$", unit):
        return re.search(r"(kg|g|ml|l)$", unit).group()
    
    return mapping.get(unit, unit)

def process_json(json_key):
    # json_key example: data/pro/json/PnP/Eastern_Cape/13_February_-_15_February_2026/page_1.json
    try:
        parts = json_key.split('/')
        # parts: ['data', 'pro', 'json', 'PnP', 'Eastern_Cape', '13_February_-_15_February_2026', 'page_1.json']
        province = parts[4]
        date_range = parts[5]
    except (IndexError, ValueError):
        print(f"Invalid JSON key structure: {json_key}")
        return

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

    # Create DataFrame
    df = pd.DataFrame(products)

    # Standardize columns (ensure all expected columns exist)
    expected_columns = [
        "product_name", "brand", "current_price", "was_price", 
        "weight_volume", "unit", "deal_type", "multi_buy_quantity", 
        "bounding_box", "group_id"
    ]
    
    for col in expected_columns:
        if col not in df.columns:
            df[col] = None

    # Apply cleaning/normalization
    df['brand'] = df['brand'].apply(normalize_brand)
    df['unit'] = df['unit'].apply(normalize_unit)
    
    # Force weight_volume to string as requested
    df['weight_volume'] = df['weight_volume'].astype(str).replace('None', None).replace('nan', None)
    
    # Fill missing group_id with 'UNKNOWN'
    df['group_id'] = df['group_id'].fillna('UNKNOWN')
    
    # Add partition columns
    df['province'] = province
    df['date_range'] = date_range
    df['source_file'] = os.path.basename(json_key)

    # Reorder columns to a consistent schema
    df = df[expected_columns + ['province', 'date_range', 'source_file']]

    # Write as Parquet to clean folder
    # We partition by province and date_range for Athena performance
    output_path = f"s3://{S3_BUCKET}/{OUTPUT_PREFIX}"
    
    print(f"Writing Parquet to: {output_path}")
    try:
        wr.s3.to_parquet(
            df=df,
            path=output_path,
            dataset=True,
            partition_cols=["province", "date_range"],
            mode="overwrite_partitions", # Only overwrite the specific partition we are working on
            database=None, # Optionally set for Glue Catalog
            table=None     # Optionally set for Glue Catalog
        )
    except Exception as e:
        print(f"Error writing Parquet: {e}")

def lambda_handler(event, context):
    """
    Triggered by S3 ObjectCreated events for JSON files.
    Cleans data AND invokes the Cropper Lambda.
    """
    for record in event.get('Records', []):
        key = record['s3']['object']['key']
        
        if key.endswith('.json') and 'data/pro/json/PnP/' in key:
            print(f"Cleaning and converting to Parquet: {key}")
            process_json(key)
            
            # Trigger Cropper Lambda (Passing the same S3 event)
            try:
                cropper_function_name = os.environ.get("CROPPER_LAMBDA_NAME")
                if cropper_function_name:
                    print(f"Invoking Cropper Lambda: {cropper_function_name}")
                    lambda_client.invoke(
                        FunctionName=cropper_function_name,
                        InvocationType='Event', # Asynchronous
                        Payload=json.dumps(event)
                    )
                else:
                    print("CROPPER_LAMBDA_NAME environment variable not set.")
            except Exception as e:
                print(f"Error invoking Cropper Lambda: {e}")
            
    return {
        'statusCode': 200,
        'body': json.dumps('Data cleaning complete and Cropper invoked')
    }
