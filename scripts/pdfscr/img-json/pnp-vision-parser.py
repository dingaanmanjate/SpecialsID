import os
import json
import time
from pathlib import Path
from google import genai
from dotenv import load_dotenv
from google.genai import types
from PIL import Image

# 1. Configuration
INTERIM_DIR = Path("data/interim/images")
OUTPUT_DIR = Path("data/pro/json")
MODELS = ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-3-flash-preview"]
current_model_index = 0

# 2. Setup Gemini
load_dotenv()
client = genai.Client()

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

def get_current_model():
    global current_model_index
    return MODELS[current_model_index]

def rotate_model():
    global current_model_index
    current_model_index = (current_model_index + 1) % len(MODELS)
    print(f"🔄 Rotating to model: {MODELS[current_model_index]}")
    if current_model_index == 0:
        print("⚠️ All models have been tried. exiting...")
        exit(1)
        

def process_image(image_path: Path):
    # Determine output path
    relative_path = image_path.relative_to(INTERIM_DIR)
    output_path = OUTPUT_DIR / relative_path.with_suffix(".json")
    
    if output_path.exists():
        print(f"⏩ Skipping (already exists): {relative_path}")
        return "skipped"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    max_retries = len(MODELS)
    attempts = 0

    while attempts < max_retries:
        model_id = get_current_model()
        try:
            print(f"🔍 Processing: {relative_path} (Model: {model_id})")
            img = Image.open(image_path)
            
            response = client.models.generate_content(
                model=model_id,
                contents=[img, "Extract grocery data according to system instructions."],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json"
                )
            )

            # Handle parsed response or raw text
            data = response.parsed if hasattr(response, 'parsed') and response.parsed is not None else None
            
            if data is None and hasattr(response, 'text') and response.text:
                try:
                    data = json.loads(response.text)
                except json.JSONDecodeError:
                    pass

            if data:
                with open(output_path, "w") as f:
                    json.dump(data, f, indent=4)
                print(f"✅ Saved to {output_path}")
                return "processed"
            else:
                print(f"⚠️ No data extracted for {image_path.name}")
                return "failed"

        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "resource_exhausted" in error_msg or "quota" in error_msg:
                print(f"⏳ Rate limit hit for {model_id}...")
                rotate_model()
                attempts += 1
                time.sleep(2) 
                continue
            else:
                print(f"❌ Error processing {image_path} with {model_id}: {e}")
                return "failed"
    
    print(f"❌ Failed after trying all models.")
    return "failed"

def main():
    if not INTERIM_DIR.exists():
        print(f"❌ Interim directory not found: {INTERIM_DIR}")
        return

    # Find all images
    image_files = sorted(list(INTERIM_DIR.rglob("*.jpg")) + list(INTERIM_DIR.rglob("*.png")))
    total_files = len(image_files)
    print(f"🚀 Found {total_files} images to process.")

    newly_processed = 0
    skipped_count = 0
    failed_count = 0

    for i, img_path in enumerate(image_files, 1):
        result = process_image(img_path)
        
        if result == "processed":
            newly_processed += 1
            # Rate limiting - 1 second between calls to be safe
            time.sleep(1) 
        elif result == "skipped":
            skipped_count += 1
        else:
            failed_count += 1
        
        if i % 10 == 0:
            print(f"📊 Progress: {i}/{total_files} images checked.")

    print(f"\n✨ Done!")
    print(f"✅ Newly processed: {newly_processed}")
    print(f"⏩ Skipped:         {skipped_count}")
    print(f"❌ Failed:          {failed_count}")
    print(f"📊 Total checked:   {total_files}")

if __name__ == "__main__":
    main()
