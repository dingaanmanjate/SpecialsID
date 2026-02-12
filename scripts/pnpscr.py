import os
import requests
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

# Configuration
BASE_URL = "https://www.pnp.co.za/catalogues"
ROOT_DIR = "data/raw/PnP"


def download_catalogues():
    with sync_playwright() as p:
        # Launch headed to see what's happening if it fails
        context = p.chromium.launch_persistent_context( user_data_dir="./user_data", headless=False, 
                                                       args=[
                                                        "--disable-blink-features=AutomationControlled",
                                                        "--excludeSwitches=enable-automation",
                                                            "--use-mock-keychain" # Useful for Arch Linux keyring issues
                                                        ]) 
        # Mimic a real browser to avoid blocks
        #context = browser.new_context(
        #    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        #    viewport={'width': 1920, 'height': 1080}
        #)
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        page = context.new_page()
        stealth_sync(page) # This applies all stealth fixes to the page
        
        print(f"Opening {BASE_URL}...")
        # Use a longer timeout and wait for till
        page.goto(BASE_URL, wait_until="commit", timeout=60000)

        # Try a more generic selector if .catalogue-card is missing
        # We look for the 'pdfdownload' class seen in your inspector image
        try:
            page.wait_for_selector(".pdfdownload", timeout=15000)
        except:
            print("Standard selector failed. Attempting to find any download buttons...")
            # Fallback: Wait for any button that contains region text
            page.wait_for_selector("text=Gauteng", timeout=10000)

        # Locate all 'cards' or containers holding the download buttons
        # Based on your image, buttons are inside a div with class 'pdfdownload'
        download_containers = page.query_selector_all("div.pdfdownload")

        for container in download_containers:
            # Move up to the parent to find the date
            parent = container.evaluate_handle("el => el.closest('.content')")
            date_element = parent.query_selector(".cat-validity-date")
            date_text = date_element.inner_text() if date_element else "unknown_date"
            date_slug = date_text.replace(" ", "_").replace("-", "_")

            # Find all regional links inside this specific container
            links = container.query_selector_all("a")
            for link in links:
                province = link.inner_text().strip()
                url = link.get_attribute("href")

                if url and ".pdf" in url.lower():
                    target_dir = os.path.join(ROOT_DIR, province)
                    os.makedirs(target_dir, exist_ok=True)
                    
                    file_path = os.path.join(target_dir, f"{date_slug}.pdf")
                    if not os.path.exists(file_path):
                        print(f"Found {province} ({date_text}). Downloading...")
                        r = requests.get(url)
                        with open(file_path, "wb") as f:
                            f.write(r.content)

        browser.close()

if __name__ == "__main__":
    download_catalogues()