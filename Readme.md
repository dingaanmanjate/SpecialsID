##SpecialsID##
A program for getting the latest specials from the popular local markets (currently Pick n Pay)

locally using the developer's . ~/.venv/bin/activate

will need execution:
sudo pacman -S poppler #for pdf2image dependency satisfaction

pip install -r requirements.txt

playwright install-deps
playwright install chromium # for the crawling.


run in teh venv:
python3 scripts/pnpscr.py
#will automatically download all the pdf through dynamic scraping, skipping the shopnow button

#ignore the pnpscr warnigns, the IDE does nto understand my complex though process. 