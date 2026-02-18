#!/bin/bash
# Exit on error and print commands
set -ex

# Configuration
REGION="af-south-1"
PROJECT_NAME="specials-id"
PROFILE=${1:-$AWS_PROFILE} # Use first argument or AWS_PROFILE env var

# Helper function to run AWS commands with profile if provided
aws_cmd() {
    if [ -n "$PROFILE" ]; then
        aws --profile "$PROFILE" "$@"
    else
        aws "$@"
    fi
}

echo "🚀 Starting Docker Build & Push for region: ${REGION}"
if [ -n "$PROFILE" ]; then
    echo "🔑 Using AWS Profile: ${PROFILE}"
fi

# Get AWS Account ID
ACCOUNT_ID=$(aws_cmd sts get-caller-identity --query Account --output text)

if [ -z "$ACCOUNT_ID" ]; then
    echo "❌ Error: Could not get AWS Account ID. Are your credentials set?"
    echo "Try running: aws-vault exec <your-profile> -- ./push_images.sh"
    exit 1
fi

ECR_URL="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# 1. Login to ECR
echo "🔐 Logging into ECR..."
aws_cmd ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_URL}

# Array of services to process
SERVICES=("scraper" "pdf_converter" "vision_parser" "cropper")

for SERVICE in "${SERVICES[@]}"; do
    REPO_NAME="${PROJECT_NAME}-${SERVICE}"
    FULL_URL="${ECR_URL}/${REPO_NAME}:latest"

    echo "----------------------------------------------------"
    echo "📦 Processing: ${SERVICE}"
    
    # 2. Ensure Repository Exists
    aws_cmd ecr describe-repositories --repository-names ${REPO_NAME} --region ${REGION} > /dev/null 2>&1 || aws_cmd ecr create-repository --repository-name ${REPO_NAME} --region ${REGION}

    # 3. Build Image
    echo "🛠 Building image for ${SERVICE}..."
    docker build --platform linux/amd64 -t ${REPO_NAME} ./infrastructure/lambda_images/${SERVICE}

    # 4. Tag Image
    echo "🏷 Tagging image..."
    docker tag ${REPO_NAME}:latest ${FULL_URL}

    # 5. Push Image
    echo "📤 Pushing image to ECR..."
    docker push ${FULL_URL}

    echo "✅ Finished ${SERVICE}"
done

echo "----------------------------------------------------"
echo "✨ All images pushed to ECR!"
echo "👉 You can now run: cd infrastructure && terraform apply"
