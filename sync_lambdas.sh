#!/bin/bash

# Script to sync lambda files to their respective docker build directories
# This ensures Docker can see the files (as they must be in the same context)

cp scripts/scr/pnpscrLambda.py infrastructure/lambda_images/scraper/
cp scripts/pdfscr/pdf-img/gen_pdf_imgLambda.py infrastructure/lambda_images/pdf_converter/
cp scripts/pdfscr/img-json/pnp-vision-parserLambda.py infrastructure/lambda_images/vision_parser/
cp scripts/pdfscr/img-shr/pnp-cropperLambda.py infrastructure/lambda_images/cropper/

echo "✅ Lambda scripts synced to infrastructure/lambda_images/"
