provider "aws" {
  region = var.aws_region
}

# --- Existing S3 Bucket ---
data "aws_s3_bucket" "data_bucket" {
  bucket = var.existing_bucket_name
}

# --- Import existing resources ---
import {
  to = aws_ecr_repository.repos["data_cleaner"]
  id = "specials-id-data_cleaner"
}

# --- ECR Repositories for Dockerized Lambdas ---
resource "aws_ecr_repository" "repos" {
  for_each = toset(["scraper", "pdf_converter", "vision_parser", "cropper", "data_cleaner"])
  name     = "${var.project_name}-${each.key}"
  force_delete = true
}

# --- IAM Role for Lambda Functions ---
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

# CloudWatch Logs Permission
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# S3 Access Policy
resource "aws_iam_policy" "lambda_s3_policy" {
  name        = "${var.project_name}-s3-policy"
  description = "Permissions for S3 bucket access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:HeadObject"
        ]
        Effect   = "Allow"
        Resource = [
          "${data.aws_s3_bucket.data_bucket.arn}",
          "${data.aws_s3_bucket.data_bucket.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_s3" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_s3_policy.arn
}

# SSM Permission for Vision Parser (to read Gemini Key)
resource "aws_iam_policy" "lambda_ssm_policy" {
  name        = "${var.project_name}-ssm-policy"
  description = "Permissions for SSM parameter access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "ssm:GetParameter"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:ssm:${var.aws_region}:*:parameter${var.gemini_api_key_ssm_name}"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_ssm" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_ssm_policy.arn
}

resource "aws_iam_policy" "lambda_invoke_policy" {
  name        = "${var.project_name}-invoke-policy"
  description = "Allow lambda to invoke itself for recursive crawling"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "lambda:InvokeFunction"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_invoke" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_invoke_policy.arn
}

resource "aws_lambda_function" "scraper" {
  function_name = "${var.project_name}-scraper"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.repos["scraper"].repository_url}:latest"
  timeout       = 300
  memory_size   = 2048

  environment {
    variables = {
      S3_BUCKET_NAME = data.aws_s3_bucket.data_bucket.id
    }
  }
}

resource "aws_lambda_function" "pdf_converter" {
  function_name = "${var.project_name}-pdf-converter"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.repos["pdf_converter"].repository_url}:latest"
  timeout       = 300
  memory_size   = 1024

  environment {
    variables = {
      S3_BUCKET_NAME = data.aws_s3_bucket.data_bucket.id
    }
  }
}

resource "aws_lambda_function" "vision_parser" {
  function_name = "${var.project_name}-vision-parser"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.repos["vision_parser"].repository_url}:latest"
  timeout       = 900
  memory_size   = 1024

  environment {
    variables = {
      S3_BUCKET_NAME          = data.aws_s3_bucket.data_bucket.id
      GEMINI_API_KEY_SSM_NAME = var.gemini_api_key_ssm_name
    }
  }
}

resource "aws_lambda_function" "cropper" {
  function_name = "${var.project_name}-cropper"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.repos["cropper"].repository_url}:latest"
  timeout       = 300
  memory_size   = 1024

  environment {
    variables = {
      S3_BUCKET_NAME = data.aws_s3_bucket.data_bucket.id
    }
  }
}

resource "aws_lambda_function" "data_cleaner" {
  function_name = "${var.project_name}-data-cleaner"
  role          = aws_iam_role.lambda_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.repos["data_cleaner"].repository_url}:latest"
  timeout       = 300
  memory_size   = 2048 # Pandas/awswrangler need more memory

  environment {
    variables = {
      S3_BUCKET_NAME       = data.aws_s3_bucket.data_bucket.id
      CROPPER_LAMBDA_NAME = aws_lambda_function.cropper.function_name
    }
  }
}

# --- S3 Event Triggers ---

resource "aws_lambda_permission" "allow_s3_converter" {
  statement_id  = "AllowExecutionFromS3"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pdf_converter.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = data.aws_s3_bucket.data_bucket.arn
}

resource "aws_lambda_permission" "allow_s3_parser" {
  statement_id  = "AllowExecutionFromS3"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.vision_parser.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = data.aws_s3_bucket.data_bucket.arn
}

resource "aws_lambda_permission" "allow_data_cleaner_to_invoke_cropper" {
  statement_id  = "AllowDataCleanerInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cropper.function_name
  principal     = "lambda.amazonaws.com"
  source_arn    = aws_lambda_function.data_cleaner.arn
}

resource "aws_lambda_permission" "allow_s3_cleaner" {
  statement_id  = "AllowExecutionFromS3"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.data_cleaner.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = data.aws_s3_bucket.data_bucket.arn
}

resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = data.aws_s3_bucket.data_bucket.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.pdf_converter.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "data/raw/PnP/"
    filter_suffix       = ".pdf"
  }

  lambda_function {
    lambda_function_arn = aws_lambda_function.vision_parser.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "data/interim/images/PnP/"
    filter_suffix       = ".jpg"
  }

  lambda_function {
    lambda_function_arn = aws_lambda_function.data_cleaner.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "data/pro/json/PnP/"
    filter_suffix       = ".json"
  }

  depends_on = [
    aws_lambda_permission.allow_s3_converter,
    aws_lambda_permission.allow_s3_parser,
    aws_lambda_permission.allow_s3_cleaner
  ]
}

# --- Schedule for Scraper (Daily) ---
resource "aws_cloudwatch_event_rule" "daily_scrape" {
  name                = "${var.project_name}-daily-scrape"
  description         = "Triggers the scraper every morning"
  schedule_expression = "cron(0 6 * * ? *)"
}

resource "aws_cloudwatch_event_target" "trigger_scraper" {
  rule      = aws_cloudwatch_event_rule.daily_scrape.name
  target_id = "ScraperLambda"
  arn       = aws_lambda_function.scraper.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scraper.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_scrape.arn
}

# --- AWS Glue Data Catalog & Crawler ---

resource "aws_glue_catalog_database" "specials_db" {
  name = "${var.project_name}_db"
}

resource "aws_iam_role" "glue_role" {
  name = "${var.project_name}-glue-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "glue.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_policy" "glue_s3_policy" {
  name        = "${var.project_name}-glue-s3-policy"
  description = "Permissions for Glue to access S3 data"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Effect   = "Allow"
        Resource = [
          "${data.aws_s3_bucket.data_bucket.arn}",
          "${data.aws_s3_bucket.data_bucket.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "glue_s3" {
  role       = aws_iam_role.glue_role.name
  policy_arn = aws_iam_policy.glue_s3_policy.arn
}

resource "aws_glue_crawler" "data_crawler" {
  database_name = aws_glue_catalog_database.specials_db.name
  name          = "${var.project_name}-clean-data-crawler"
  role          = aws_iam_role.glue_role.arn

  s3_target {
    path = "s3://${data.aws_s3_bucket.data_bucket.id}/data/clean/PnP/"
  }

  schema_change_policy {
    delete_behavior = "LOG"
    update_behavior = "UPDATE_IN_DATABASE"
  }
}
