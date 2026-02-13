import os
import json
from pathlib import Path
from PIL import Image

# 1. Configuration
INTERIM_DIR = Path("data/interim/images")
JSON_DIR = Path("data/pro/json")
OUTPUT_DIR = Path("data/shr/products")
PADDING_PERCENT = 0.10  # 10% padding for better leverage/framing

def crop_products(image_path: Path, json_path: Path):
    if not json_path.exists():
        # print(f"⏩ Skipping: JSON not found for {image_path}")
        return

    # Load bounding boxes
    try:
        with open(json_path, "r") as f:
            products = json.load(f)
    except Exception as e:
        print(f"❌ Error reading {json_path}: {e}")
        return

    if not products:
        return

    # Open image
    try:
        img = Image.open(image_path)
        width, height = img.size
    except Exception as e:
        print(f"❌ Error opening {image_path}: {e}")
        return

    # Create output directory for this specific page
    relative_path = image_path.relative_to(INTERIM_DIR).with_suffix("")
    page_output_dir = OUTPUT_DIR / relative_path
    
    # Check if already processed to avoid redundant work
    if page_output_dir.exists() and any(page_output_dir.iterdir()):
        print(f"⏩ Skipping {image_path.name} (Already cropped)")
        return

    page_output_dir.mkdir(parents=True, exist_ok=True)

    print(f"✂️ Cropping {len(products)} products from {image_path.name}...")

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

        # Crop and save
        try:
            cropped_img = img.crop((left, top, right, bottom))
            
            # Sanitize product name for filename
            raw_name = product.get("product_name", f"product_{i}")
            prod_name = "".join([c if c.isalnum() or c in " _-" else "_" for c in raw_name])
            prod_name = prod_name.replace(" ", "_").strip("_")[:50] # Limit length
            
            crop_filename = f"{i}_{prod_name}.jpg"
            crop_path = page_output_dir / crop_filename
            
            cropped_img.save(crop_path, quality=90)
        except Exception as e:
            print(f"❌ Failed to crop product {i} in {image_path.name}: {e}")

def main():
    if not INTERIM_DIR.exists():
        print(f"❌ Interim directory not found: {INTERIM_DIR}")
        return

    # Find all images recursively
    image_files = sorted(list(INTERIM_DIR.rglob("*.jpg")) + list(INTERIM_DIR.rglob("*.png")))
    total_files = len(image_files)
    print(f"🚀 Found {total_files} pages to process.")

    for img_path in image_files:
        # Construct corresponding JSON path
        # Assuming the structure in data/pro/json/PnP matches data/interim/images/PnP
        relative_to_interim = img_path.relative_to(INTERIM_DIR)
        json_path = JSON_DIR / relative_to_interim.with_suffix(".json")
        
        crop_products(img_path, json_path)

    print(f"\n✨ Cropping complete!")

if __name__ == "__main__":
    main()
