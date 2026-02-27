# SpecialsID - Technical Architecture & Repository Map

This document provides a technical deep-dive into the SpecialsID system architecture, data pipeline, and repository structure. It is maintained by Gemini CLI.

## 1. System Architecture Overview

**SpecialsID** is a fully automated, event-driven, serverless data processing pipeline deployed on AWS. Its primary function is to extract structured product data from retail promotional flyers (PDFs) and make it available for large-scale analysis via a queryable data lake.

The architecture is orchestrated through a series of AWS Lambda functions triggered by S3 events and a scheduled CloudWatch rule. Data flows through several stages of transformation, moving between S3 prefixes that represent its state (`raw`, `interim`, `pro`, `clean`, `shr`). The final output is a partitioned Parquet dataset in S3, cataloged by AWS Glue and queryable with Amazon Athena.

### Core Technologies:
- **Infrastructure as Code:** Terraform
- **Compute:** AWS Lambda (containerized Python runtimes)
- **Storage:** AWS S3
- **Orchestration:** S3 Events, CloudWatch Events
- **Data Catalog & Querying:** AWS Glue, Amazon Athena
- **AI/Vision:** Google Gemini API (via `google-generativeai`)
- **Data Processing:** Pandas, AWS Data Wrangler (`awswrangler`)
- **Web Scraping:** Playwright with Stealth
- **PDF/Image Processing:** `pdf2image` (Poppler), Pillow (PIL)

---

## 2. End-to-End Data Pipeline

The pipeline consists of five distinct Lambda functions, each responsible for a specific stage of data transformation.

### **Stage 1: Scraping (Scheduled)**
- **Trigger:** AWS CloudWatch Event (Scheduled `cron(0 6 * * ? *)` - 6 AM UTC daily).
- **Lambda:** `specials-id-scraper`
- **Source Code:** `infrastructure/lambda_images/scraper/pnpscrLambda.py`
- **Function:**
    1.  Launches a headless Chromium browser using Playwright.
    2.  Navigates to `pnp.co.za/catalogues`.
    3.  Locates and identifies all available PDF flyer download links.
    4.  Checks if a flyer already exists in S3 to prevent re-processing.
    5.  Downloads new PDF files to the Lambda's `/tmp` storage.
    6.  Uploads the raw PDFs to S3.
- **S3 Output:** `s3://{bucket}/data/raw/PnP/{province}/{date_slug}.pdf`

### **Stage 2: PDF to Image Conversion**
- **Trigger:** S3 `ObjectCreated` event on `data/raw/PnP/` with a `.pdf` suffix.
- **Lambda:** `specials-id-pdf-converter`
- **Source Code:** `infrastructure/lambda_images/pdf_converter/gen_pdf_imgLambda.py`
- **Function:**
    1.  Downloads the triggering PDF from S3.
    2.  Uses `pdf2image` to convert each page of the PDF into a high-resolution JPEG image (300 DPI) suitable for vision analysis.
    3.  Uploads each page image to S3.
- **S3 Output:** `s3://{bucket}/data/interim/images/PnP/{province}/{flyer_name}/page_{i}.jpg`

### **Stage 3: Vision AI Data Extraction**
- **Trigger:** S3 `ObjectCreated` event on `data/interim/images/PnP/` with a `.jpg` suffix. Can also be self-triggered for batch processing.
- **Lambda:** `specials-id-vision-parser`
- **Source Code:** `infrastructure/lambda_images/vision_parser/pnp-vision-parserLambda.py`
- **Function:**
    1.  Downloads the triggering page image from S3.
    2.  Sends the image to the Google Gemini API with a detailed system prompt instructing it to extract product information as structured JSON.
    3.  **Resilience:**
        - **API Key Rotation:** Fetches multiple Gemini API keys from AWS SSM. Rotates to the next key upon encountering a rate limit error (429).
        - **Model Fallback:** Tries a list of Gemini models in sequence if a request fails.
        - **Recursive Batch Processing:** If invoked in "discovery" mode, it processes a batch of images and re-invokes itself with a continuation token to avoid the 15-minute Lambda timeout.
    4.  Saves the extracted, raw JSON data to S3.
- **S3 Output:** `s3://{bucket}/data/pro/json/PnP/{province}/{flyer_name}/page_{i}.json`

### **Stage 4: Data Cleaning & Structuring**
- **Trigger:** S3 `ObjectCreated` event on `data/pro/json/PnP/` with a `.json` suffix.
- **Lambda:** `specials-id-data-cleaner`
- **Source Code:** `infrastructure/lambda_images/data_cleaner/pnp-cleanerLambda.py`
- **Function:**
    1.  Reads the raw JSON from S3 into a Pandas DataFrame.
    2.  Performs data cleaning: normalizes brand names, standardizes units, ensures schema consistency.
    3.  Adds partition columns (`province`, `date_range`) derived from the S3 key.
    4.  Uses `awswrangler` to write the cleaned data as a **partitioned Parquet file** to the `clean` data lake directory. This format is highly optimized for Athena queries.
    5.  Asynchronously invokes the `cropper` Lambda, passing the original S3 event to start the parallel image cropping process.
- **S3 Output:** `s3://{bucket}/data/clean/PnP/province={province}/date_range={date_range}/{uuid}.parquet`

### **Stage 5: Product Image Cropping (Parallel Task)**
- **Trigger:** Invoked directly by the `data-cleaner` Lambda.
- **Lambda:** `specials-id-cropper`
- **Source Code:** `infrastructure/lambda_images/cropper/pnp-cropperLambda.py`
- **Function:**
    1.  Receives the event for a processed JSON file.
    2.  Reads the JSON to get product bounding boxes and the corresponding full-size page image.
    3.  For each product, it uses Pillow to crop the product's image from the main page image, adding 10% padding.
    4.  Uploads each cropped product image to S3. These images can be used by a frontend application or for further model training.
- **S3 Output:** `s3://{bucket}/data/shr/products/PnP/{province}/{flyer_name}/page_{i}/{product_name}.jpg`

---

## 3. Data Lake & Analytics

- **AWS Glue Crawler:** The `specials-id-clean-data-crawler` is configured in Terraform to run on the `s3://{bucket}/data/clean/PnP/` path.
- **Function:** It automatically discovers the schema of the Parquet files and detects the `province` and `date_range` partitions. It registers this metadata in the `specials-id_db` Glue Data Catalog database.
- **Amazon Athena:** Once cataloged, the data can be queried using standard SQL via Athena, leveraging the performance benefits of the Parquet format and partitioning.

### Final Data Schema (`clean` Parquet files)
| Column Name          | Data Type | Description                                                    |
| -------------------- | --------- | -------------------------------------------------------------- |
| `product_name`       | `string`  | Full name of the product.                                      |
| `brand`              | `string`  | Normalized brand name.                                         |
| `current_price`      | `float`   | The price of the special.                                      |
| `was_price`          | `float`   | The previous price, if available.                              |
| `weight_volume`      | `string`  | The numeric part of the weight/volume (e.g., "500").           |
| `unit`               | `string`  | Normalized unit of measurement (e.g., 'g', 'kg', 'litre').     |
| `deal_type`          | `string`  | Type of promotion ('Any 2', 'Combo', 'Smart Shopper').         |
| `multi_buy_quantity` | `int`     | Number of items required for the deal (e.g., 2 for "Any 2").   |
| `bounding_box`       | `array`   | `[ymin, xmin, ymax, xmax]` normalized coordinates.             |
| `group_id`           | `string`  | ID to link items in a combo deal.                              |
| **`province`**       | `string`  | **Partition Column:** The province for the flyer.              |
| **`date_range`**     | `string`  | **Partition Column:** The validity date range for the flyer.   |
| `source_file`        | `string`  | The source JSON file the record came from.                     |

---

## 4. Repository Structure

- `infrastructure/`: Contains all Terraform (`.tf`) files for defining the AWS infrastructure.
    - `lambda_images/`: Source code for the five Lambda functions, each with its own `Dockerfile` and `requirements.txt`.
- `scripts/`: Local Python scripts that mirror the Lambda function logic for development and testing.
- `data/`: Local data storage, ignored by Git. Maps to S3 structure (`raw`, `interim`, `pro`, `clean`, `shr`).
- `*.sh`: Utility scripts for building and pushing Docker images (`push_images.sh`), syncing data (`sync.sh`), etc.
- `GEMINI_REPO_MAP.md`: This file.
