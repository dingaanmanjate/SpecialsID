variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "af-south-1"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "<Project-name>"
}

variable "existing_bucket_name" {
  description = "The name of the existing S3 bucket to use"
  type        = string
  default     = "<bucket-name>"
}

variable "gemini_api_key_ssm_name" {
  description = "SSM Parameter name for Gemini API Key"
  type        = string
  default     = "<Parameter-name>"
}
