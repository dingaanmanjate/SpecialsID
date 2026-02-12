##SpecialsID##
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


Extended a new script to conver teh pdfs to 
python3 scripts/pdfscr/pdf-img/gen_pdf_img.py