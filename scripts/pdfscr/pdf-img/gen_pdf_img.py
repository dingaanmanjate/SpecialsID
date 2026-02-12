import os
from pathlib import Path
from pdf2image import convert_from_path

# 1. Setup Path Independence
# This locates the 'SpecialsID' root folder relative to this script's location
SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[3]  # Go up three levels (from scripts/pdfscr/pdf-img/ to SpecialsID/)

# 2. Define Medallion Layer Paths
BRONZE_DIR = PROJECT_ROOT / "data" / "raw" / "PnP"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim" / "images" / "PnP"

def convert_all_flyers():
    print(f"Project Root: {PROJECT_ROOT}")
    
    # Ensure the base interim directory exists
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    # 3. Iterate through Provincial Folders
    if not BRONZE_DIR.exists():
        print(f"Error: {BRONZE_DIR} not found. Check your directory structure.")
        return

    for province_path in BRONZE_DIR.iterdir():
        if province_path.is_dir():
            province_name = province_path.name
            print(f"\nScanning Province: {province_name}")

            # 4. Find all PDFs in the Province folder
            for pdf_file in province_path.glob("*.pdf"):
                print(f"  Processing: {pdf_file.name}")
                
                # Create a specific folder for this flyer's images
                # e.g., data/interim/images/PnP/Gauteng/Weekly_Specials_Feb/
                flyer_folder_name = pdf_file.stem  # Filename without .pdf
                output_path = INTERIM_DIR / province_name / flyer_folder_name
                output_path.mkdir(parents=True, exist_ok=True)

                try:
                    # 5. Convert PDF to High-Res JPEG (300 DPI for AI clarity)
                    images = convert_from_path(str(pdf_file), dpi=300)
                    
                    for i, image in enumerate(images):
                        image_filename = f"page_{i + 1}.jpg"
                        image.save(output_path / image_filename, "JPEG")
                        print(f"    - Saved Page {i + 1}")
                
                except Exception as e:
                    print(f"    - Error converting {pdf_file.name}: {e}")

if __name__ == "__main__":
    convert_all_flyers()