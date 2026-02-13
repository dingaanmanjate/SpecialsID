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