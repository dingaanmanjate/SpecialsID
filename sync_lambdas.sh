#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "🔍 Verifying and syncing lambda scripts..."

# Define source and destination mappings
declare -A LAMBDAS=(
    ["scripts/scr/pnpscrLambda.py"]="infrastructure/lambda_images/scraper/"
    ["scripts/pdfscr/pdf-img/gen_pdf_imgLambda.py"]="infrastructure/lambda_images/pdf_converter/"
    ["scripts/pdfscr/img-json/pnp-vision-parserLambda.py"]="infrastructure/lambda_images/vision_parser/"
    ["scripts/pdfscr/img-shr/pnp-cropperLambda.py"]="infrastructure/lambda_images/cropper/"
)

# Iterate over the files and copy them
for src in "${!LAMBDAS[@]}"; do
    dest_dir=${LAMBDAS[$src]}
    
    if [ ! -f "$src" ]; then
        echo "❌ Error: Source file not found: $src"
        exit 1
    fi
    
    echo "  -> Copying $src to $dest_dir"
    cp "$src" "$dest_dir"
done

echo "✅ Lambda scripts synced successfully to infrastructure/lambda_images/"
