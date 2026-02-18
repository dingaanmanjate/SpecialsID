#!/bin/bash

# This script imports the ECR repositories (which were created by push_images.sh)
# into the Terraform state. This should only be run once.

# Ensure you are in the correct directory
if [ ! -f "main.tf" ]; then
    echo "❌ Please run this script from the 'infrastructure' directory."
    exit 1
fi

PROJECT_NAME="specials-id"
SERVICES=("scraper" "pdf_converter" "vision_parser" "cropper")
PROFILE=${1:-$AWS_PROFILE}

# Helper function to run Terraform commands
terraform_cmd() {
    if [ -n "$PROFILE" ]; then
        aws-vault exec "$PROFILE" -- terraform "$@"
    else
        terraform "$@"
    fi
}

echo "🔄 Importing ECR repositories into Terraform state..."

for SERVICE in "${SERVICES[@]}"; do
    REPO_NAME="${PROJECT_NAME}-${SERVICE}"
    echo "  -> Importing ${REPO_NAME}"
    terraform_cmd import "aws_ecr_repository.repos["${SERVICE}"]" "${REPO_NAME}"
done

echo "✅ Import complete! You can now run 'terraform apply' again."
