# 🚀 Project SpecialsID

**A Fully Serverless, Event-Driven Intelligent Retail Analytics Platform**

Project SpecialsID is an end-to-end data pipeline and intelligent dashboard designed to scrape, parse, clean, and visualize retail specials (currently Pick n Pay) across South Africa. The architecture strictly adheres to Cloud Solutions Architect best practices, heavily leveraging the AWS Free Tier, Serverless event-driven processing, and Large Language Models (LLMs) for computer vision and semantic parsing.

---

## 🏗️ System Architecture

The system is built on an **Event-Driven Microservices** architecture. No EC2 instances or long-running servers are utilized in the backend. Processing is triggered exclusively by state changes in an S3 Data Lake.

### 1. Data Ingestion (Scraping)
*   **Component:** AWS Lambda (`scraper`) packaged as a Docker container.
*   **Stack:** Python, Playwright, Playwright-Stealth.
*   **Trigger:** Amazon EventBridge (Cron schedule).
*   **Operation:** Bypasses basic WAF/anti-bot mechanisms to navigate digital circulars, locates region-specific catalog data, and downloads raw PDF files.
*   **Storage:** Pushes raw PDFs to `s3://<bucket>/data/raw/PnP/{province}/`.

### 2. S3 Event Notifications & Data Transformation
The core of the pipeline is a chained execution model using `s3:ObjectCreated:*` triggers.

#### Stage A: PDF Conversion
*   **Trigger:** Creation of a `.pdf` file in the `raw` prefix.
*   **Component:** AWS Lambda (`pdf_converter`) via Docker.
*   **Stack:** `pdf2image`, Pillow.
*   **Operation:** Converts multi-page PDFs into high-resolution JPG images.
*   **Storage:** Pushes images to `s3://<bucket>/data/interim/images/PnP/`.

#### Stage B: Computer Vision Parsing (The AI Engine)
*   **Trigger:** Creation of a `.jpg` file in the `interim/images` prefix.
*   **Component:** AWS Lambda (`vision_parser`).
*   **Stack:** Google GenAI SDK (`gemini-2.5-flash`), Boto3.
*   **Operation:** Fetches the Gemini API key securely from AWS Systems Manager (SSM) Parameter Store. Uses Multimodal LLM capabilities to perform intelligent OCR and bounding box extraction. It identifies:
    *   `product_name`, `brand`, `current_price`, `was_price`
    *   `weight_volume`, `unit`
    *   `deal_type` (e.g., Multi-buy, Smart Shopper)
*   **Storage:** Pushes structured JSON to `s3://<bucket>/data/pro/json/PnP/`.

#### Stage C: Data Cleaning & Partitioning
*   **Trigger:** Creation of a `.json` file in the `pro` prefix.
*   **Component:** AWS Lambda (`data_cleaner`).
*   **Stack:** Pandas, AWS Data Wrangler (`awswrangler`).
*   **Operation:** 
    *   Merges JSON nodes.
    *   Normalizes messy date string folder names using Regex.
    *   Calculates derived metrics (e.g., `discount_pct`).
    *   **Delegation:** Triggers the `cropper` Lambda asynchronously if localized image assets of individual products are required.
*   **Storage:** Writes final data as columnar **Apache Parquet** files to `s3://<bucket>/data/clean/PnP/{province}/`.

### 3. Data Cataloging (AWS Glue)
*   An **AWS Glue Crawler** scans the `data/clean/` prefix.
*   It automatically infers schemas and builds a virtual database in the **AWS Glue Data Catalog**, making the Parquet files queryable via Amazon Athena.

---

## 📊 Streamlit Dashboard Frontend

The frontend is a multi-page application built on **Streamlit 1.54.0**, utilizing `st.navigation`. It interacts directly with the S3 clean data partitions via `awswrangler` and Boto3.

### Core Modules:

1.  **🔍 Deal Finder:** 
    *   Provides global filters (Province, Date Range) via session state.
    *   Implements an efficient wildcard search across `product_name` and `brand`.
    *   Renders data using custom, mode-agnostic CSS via `st.html()` for optimal performance and exact layout control (avoiding Streamlit markdown nesting glitches).
2.  **📊 Price Analytics:**
    *   Aggregates Pandas DataFrames to generate high-level metrics (Average Discount, Max Savings).
    *   **Brand Aggressiveness:** GroupBy operations calculate which brands offer the deepest cuts.
    *   **Expiry Timeline:** Re-queries the S3 bucket to bypass sidebar filters, providing a comprehensive view of active vs. expired deals using color-coded Pandas transformations mapped to Streamlit native charts.
3.  **🛒 AI Smart List:**
    *   Uses `gemini-2.5-flash` to parse user intent.
    *   **Ambiguity Resolution:** Expands generic terms (e.g., "stationary") into specific supermarket queries (e.g., "pen, paper, ruler").
    *   **Fuzzy Matching:** Queries the Parquet dataset against the LLM-generated keyword list.
    *   **Holistic Strategy:** Concatenates matched item names and passes them back to Gemini to generate context-aware shopping advice (meal pairings, missing staples, budget tips).

---

## 🛠️ Infrastructure as Code (Terraform)

The entire AWS backbone is defined in `infrastructure/main.tf`.

*   **ECR Repositories:** Manages 5 separate repos for the containerized lambdas (`scraper`, `pdf_converter`, `vision_parser`, `cropper`, `data_cleaner`).
*   **IAM Least Privilege:**
    *   `lambda_s3_policy`: Scoped exactly to the required bucket ARN.
    *   `lambda_ssm_policy`: Scoped exactly to the Gemini API Key Parameter ARN.
*   **Event Routing:** Manages `aws_s3_bucket_notification` for event chaining and `aws_cloudwatch_event_rule` for cron triggers.

---

## 💰 Cost Analysis & Estimations

The project is architected to minimize operational overhead. Most components fall within the **AWS Free Tier** indefinitely or incur negligible costs at this scale.

### Monthly Cost Breakdown (Estimated)

| Service | Component | Usage Estimation | Monthly Cost (Est.) |
| :--- | :--- | :--- | :--- |
| **Amazon S3** | Data Lake (Raw to Clean) | ~10GB Standard Storage | ~$0.23 |
| **AWS Lambda** | Serverless Compute | ~100k GB-seconds (Daily Cycles) | $0.00 (Free Tier) |
| **Amazon ECR** | Docker Image Hosting | 5 Repositories (~3GB total) | ~$0.30 |
| **AWS Glue** | Data Crawler | 2 DPUs * 5 mins/day | ~$2.64 |
| **Google GenAI** | Gemini 2.5 Flash API | ~1M Input Tokens / ~100k Output | ~$0.15 |
| **Streamlit Cloud** | Dashboard Hosting | Public Repository | $0.00 (Free) |
| **Total** | | | **~$3.32 / month** |

### Optimization Notes:
*   **Lambda Memory:** High-memory Lambdas (2GB for Scraper/Cleaner) are used to speed up processing, which actually reduces the total GB-seconds billed.
*   **Parquet Compression:** Using Parquet instead of CSV/JSON reduces S3 storage costs by ~80% and accelerates dashboard load times.
*   **Gemini 2.5 Flash:** Chosen specifically for its superior cost-to-performance ratio compared to the Pro model, especially for high-volume OCR tasks.

---

## 🚀 Deployment Guide (Streamlit Community Cloud)

To deploy the frontend dashboard independently of the AWS backend:

1.  **Environment Preparation:**
    Create a dedicated "Service User" in AWS IAM with the following inline policy:
    ```json
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
                "Resource": "arn:aws:s3:::special-id-data-0129"
            },
            {
                "Effect": "Allow",
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::special-id-data-0129/data/clean/PnP/*"
            }
        ]
    }
    ```
    Generate Access Keys for this user.

2.  **Streamlit Cloud Setup:**
    *   Connect your GitHub repository to [share.streamlit.io](https://share.streamlit.io).
    *   Set Main file path to `dashboard/app.py`.
    *   In **Advanced Settings > Secrets**, inject the required environment variables:
        ```toml
        GOOGLE_API_KEY = "your-gemini-key"
        AWS_ACCESS_KEY_ID = "service-user-id"
        AWS_SECRET_ACCESS_KEY = "service-user-secret"
        AWS_DEFAULT_REGION = "af-south-1"
        ```
    *   Deploy. Streamlit will install dependencies from `requirements.txt` and launch the application. The `.streamlit/config.toml` file ensures the brand theme is respected across system light/dark modes.

## 📦 Directory Structure Overview
*   `/dashboard`: Streamlit application, unified CSS, and AWS data-fetching utilities.
*   `/infrastructure`: Terraform modules and Dockerfiles for AWS Lambda images.
*   `/scripts`: Local development and testing scripts for scraping and OCR.
