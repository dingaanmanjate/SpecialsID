# SpecialsID - Gemini Repository Map

This file is maintained by Gemini CLI to document the repository structure, workflows, and changes. It is excluded from version control via `.gitignore`.

## Project Overview
**SpecialsID** is a system designed to scrape, process, and analyze retail market specials (starting with Pick n Pay). It converts scraped PDFs into images, parses them into structured JSON using Gemini AI models, and deploys the entire pipeline to AWS using Lambda functions and Terraform.

## Repository Structure

### 1. Root Directory
- `Readme.md`: Original project documentation and setup instructions.
- `requirements.txt`: Python dependencies.
- `sync.sh`: Script for syncing local data to S3.
- `push_images.sh`: Script to build and push Docker images for Lambda functions to AWS ECR.
- `sync_lambdas.sh`: (Presumed) Script to sync Lambda function code/images.

### 2. `/scripts` - Local Processing Pipeline
Mirrors the logic used in Lambda functions for local execution and testing.
- `scr/pnpscr.py`: Scraper for Pick n Pay specials.
- `pdfscr/pdf-img/`: Logic to convert PDF specials into images.
- `pdfscr/img-json/`: AI-powered parsing of images into JSON data.
- `seed/`: Likely contains initial data or seeding scripts.

### 3. `/infrastructure` - Cloud Deployment (Terraform)
- `main.tf`: Primary Terraform configuration for AWS resources (Lambda, S3, ECR, etc.).
- `lambda_images/`: Source code and Dockerfiles for the containerized Lambda functions.
    - `cropper/`: Crops images (likely for specific product isolation).
    - `pdf_converter/`: Lambda version of the PDF-to-image logic.
    - `scraper/`: Lambda version of the web scraper.
    - `vision_parser/`: Lambda version of the AI parsing logic.
- `import_ecr.sh`: Helper script for Terraform ECR state management.

### 4. Data Directories (Ignored by Git)
- `data/`: Local storage for `raw`, `interim`, `pro` (processed), and `shr` (shared/short-term) data.
- `scraping/`: Storage for scraping-specific artifacts.
- `user_data/`: Likely browser profile data for Playwright/Scraping.

---

## Change Log

### [2026-02-19] - Gemini API Key Rotation
- Modified `infrastructure/lambda_images/vision_parser/pnp-vision-parserLambda.py` to support rotating through multiple Gemini API keys.
- **Rotation Logic:** The Lambda now parses a comma-separated list of keys from the SSM parameter. If a rate limit (429) is hit, it automatically switches to the next key in the list and retries.
