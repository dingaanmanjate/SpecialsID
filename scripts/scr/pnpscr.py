import os
import requests
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# Configuration
BASE_URL = "https://www.pnp.co.za/catalogues"
ROOT_DIR = "data/raw/PnP"

def download_catalogues():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir="./user_data", 
            headless=True, 
            args=[
                "--disable-blink-features=AutomationControlled",
                "--excludeSwitches=enable-automation",
                "--use-mock-keychain"
            ]
        ) 
        
        page = context.new_page()
        Stealth().apply_stealth_sync(page)
        
        print(f"Opening {BASE_URL}...")
        try:
            page.goto(BASE_URL, wait_until="networkidle", timeout=60000)
        except Exception as e:
            print(f"Initial load timed out, attempting to proceed... {e}")

        try:
            page.wait_for_selector(".pdfdownload", timeout=20000)
        except Exception:
            print("Standard selector failed. Attempting to find regional text as fallback...")
            try:
                page.wait_for_selector("text=Gauteng", timeout=15000)
            except Exception:
                print("Failed to find download elements.")
                context.close()
                return

        download_containers = page.query_selector_all("div.pdfdownload")
        print(f"Found {len(download_containers)} download containers.")

        # Dictionary to store url -> local_path mapping to avoid redundant downloads
        url_to_path = {}
        session = requests.Session()
        # Add a basic UA to the session to look less like a script
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        })

        for container in download_containers:
            parent = container.evaluate_handle("el => el.closest('.content')")
            date_element = parent.query_selector(".cat-validity-date")
            date_text = date_element.inner_text().strip() if date_element else "unknown_date"
            
            # Remove "Valid " prefix if present to keep filenames clean
            clean_date_text = date_text.replace("Valid", "").strip()
            date_slug = "".join([c if c.isalnum() or c in ("_", "-") else "_" for c in clean_date_text])

            links = container.query_selector_all("a")
            for link in links:
                province = link.inner_text().strip().replace(" ", "_")
                href = link.get_attribute("href")
                
                if not href or ".pdf" not in href.lower() or "Shop_now" in province:
                    continue

                target_dir = os.path.join(ROOT_DIR, province)
                os.makedirs(target_dir, exist_ok=True)
                file_path = os.path.join(target_dir, f"{date_slug}.pdf")

                if os.path.exists(file_path):
                    print(f"Skipping {province} ({date_text}) - already exists.")
                    continue

                # If we already downloaded this URL in this run, just copy/link it
                if href in url_to_path:
                    print(f"Linking {province} to already downloaded file for {href}")
                    with open(url_to_path[href], 'rb') as f_src:
                        with open(file_path, 'wb') as f_dst:
                            f_dst.write(f_src.read())
                    continue

                try:
                    print(f"Downloading {province} ({date_text}) from {href}...")
                    response = session.get(href, timeout=30)
                    response.raise_for_status()
                    
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                    
                    url_to_path[href] = file_path
                    print(f"Successfully saved to {file_path}")
                except Exception as e:
                    print(f"Failed to download {province}: {e}")

        context.close()

if __name__ == "__main__":
    download_catalogues()