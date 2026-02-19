##SpecialsID## NOT PROPERLY STRUCTURED AS OF YET<FOR PLANNING PURPOSES>
A program for getting the latest specials from the popular local markets (currently Pick n Pay)

locally using the developer's . ~/.venv/bin/activate

will need execution:
sudo pacman -S poppler #for pdf2image dependency satisfaction

pip install -r requirements.txt

playwright install-deps
playwright install chromium # for the crawling.


run in teh venv:
python3 scripts/scr/pnpscr.py
#will automatically download all the pdf through dynamic scraping, skipping the shopnow button

#ignore the pnpscr warnigns, the IDE does nto understand my complex though process. 

CREATED private BUCKET:
aws-vault exec <profile> -- aws s3api create-bucket \
--bucket <bucket-name> --region af-south-1 \
--create-bucket-configuration LocationConstraint=af-south-1

ADDED Scraped pdf files to the private bucket
aws-vault exec <profile> -- aws s3 sync $PWD/data s3://<bucket-name>
in cae 3 bucket is forgotten, use:
aws-vault exec <profile> -- aws s3 ls || aws s3api list-bucket


Extended a new script to conver teh pdfs to 
python3 scripts/pdfscr/pdf-img/gen_pdf_img.py

incoporate
'''
python3 scripts/pdfscr/img-json/pnp-vision-parser.py
'''
to parse teh scraped images to json format using AI.
The scrip uses google gen AI, for image processign and a static system prompt to classifiy the products to verify repeatability. The model circulation is mainly for tackling freetier rate limits. 
Since teh classification is a model native feature, simple models are utilized, namely:
"gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-3-flash-preview"
all in the order of model performance and cost, correlated through a mathematical model from recent benchmark data. 

synced parsed json files at point time, using:
aws-vault exec <profile> -- aws s3 sync
forgot bucket name so I used:
aws-vault exec <profile> -- aws s3 ls || aws s3api list-bucket

changed directory name inconsistency from teh previous script, to remove teh "Valid_" tags, for further data integrity. 
Proceeded failed parsing, to sync files to the s3 bucket, for the data lake comcement.

added a sync.sh script for dynamic syncing, for repeatability, executed through:
./sync.sh

had to clear the bucket for a clean slate using:
aws-vault exec <profile> -- aws s3 rm s3://<bucket-name> --recursive

tehn populated teh bucket using the ./sync.sh script. 
All raw, intering and processed data has not been uploaded to the S3 bucket to undergo cleaning and further processign for s3 access. 

Prepared teh data ingestion functions for full cloud migration, changing the gen_pdf_imgLambda to reference the GEMINI_API_KEY to reference it from the SSM parameter store

added the GEMINI_API_KEY to the store using:

aws-vault exec <profile> -- aws ssm put-parameter \
    --name "/SpecialsID/gemini-api-key" \
    --value "<Actual-key>" \
    --type "SecureString"

Added script to puch Dockerfiles to ECR, compatible with aws-vault. You can run it with 
'''sh
aws-vault exec <your-profile> -- ./push_images.sh
'''

ensure docker is installe 
and run sudo systemctl start docker

final step for the full cloud deployment
cd infrastructure
aws-vault exec <your-profile> -- terraform init

./import_ecr.sh <your-profile>

aws-vault exec <your-profile> -- terraform apply

aws-vault exec capaciti -- aws lambda invoke \
  --function-name <function-name> \
  --payload fileb://<filename> \
  response.json

 aws-vault exec <profile> -- aws lambda update-function-code \
   --function-name <function-name> \
   --image-uri $(aws-vault exec <profile> -- aws ecr describe-repositories --repository-names <function-name> --query 'repositories[0].repositoryUri' --output text):latest