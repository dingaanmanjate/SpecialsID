provider "aws" {
  region = var.aws_region
}

# --- Existing S3 Bucket ---
data "aws_s3_bucket" "data_bucket" {
  bucket = var.existing_bucket_name
}

# --- ECR Repositories for Dockerized Lambdas ---
resource "aws_ecr_repository" "repos" {
  for_each = toset(["scraper", "pdf_converter", "vision_parser", "cropper"])
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
  policy_arn = "arn:aws:iam:aws:policy/service-role/AWSLambdaBasicExecutionRole"
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

# --- Lambda Functions ---

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
  timeout       = 300
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

resource "aws_lambda_permission" "allow_s3_cropper" {
  statement_id  = "AllowExecutionFromS3"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cropper.function_name
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
    lambda_function_arn = aws_lambda_function.cropper.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "data/pro/json/PnP/"
    filter_suffix       = ".json"
  }

  depends_on = [
    aws_lambda_permission.allow_s3_converter,
    aws_lambda_permission.allow_s3_parser,
    aws_lambda_permission.allow_s3_cropper
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
