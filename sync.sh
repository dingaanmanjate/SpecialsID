#!/bin/bash
# This script is used to sync the local data and frontend repository with the remote repository on s3
aws-vault exec capaciti -- aws s3 sync $PWD s3://special-id-data-0129 \
--exclude "infastructure/*" \
--exclude "user_data/*" \
--exclude "sync.sh" \
--exclude ".env" \
--exclude "README.md" \
--exclude "000metadata.json" \
--exclude "scraping/*" \
--exclude "scripts/*" \
--exclude ".gitignore" \
--exclude ".git/*" \
--exclude "requirements.txt" \
--delete

echo "Sync completed successfully!"