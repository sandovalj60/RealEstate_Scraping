import csv
import time
import argparse
import re
from datetime import date, datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from urllib.parse import quote_plus

def load_existing(csv_file):
    existing = {}
    try:
        with open(csv_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = row["Link"]
                existing[key] = row
    except FileNotFoundError:
        pass
    return existing

def extract_number(text):
    match = re.search(r"\d+", text)
    return int(match.group()) if match else 0

def normalize_type(raw_type):
    raw = raw_type.lower()
    if "house" in raw:
        return "House"
    elif "apartment" in raw:
        return "Apartment"
    elif "unit" in raw:
        return "Unit"
    elif "townhouse" in raw:
        return "Townhouse"
    elif "villa" in raw:
        return "Villa"
    elif "duplex" in raw:
        return "Duplex"
    elif "studio" in raw:
        return "Studio"
    else:
        return raw_type.strip().title()

def scrape_page(driver, url):
    driver.get(url)
    time.sleep(5)
    return driver.find_elements(By.CLASS_NAME, "residential-card__content-wrapper")

def extract_listing(card):
    try:
        address_el = card.find_element(By.CLASS_NAME, "residential-card__address-heading")
        address = address_el.text
        link = address_el.find_element(By.TAG_NAME, "a").get_attribute("href")
        full_link = "https://www.realestate.com.au" + link

        # Asking price
        try:
            price_raw = card.find_element(By.CLASS_NAME, "residential-card__price").text
            price_clean = re.sub(r"[^\d]", "", price_raw)
            asking_price = int(price_clean) if price_clean else 0
        except:
            asking_price = 0

        # Features
        features = card.find_elements(By.CSS_SELECTOR, "ul.residential-card__primary li")
        beds = baths = cars = area = 0
        for f in features:
            label = f.get_attribute("aria-label").lower()
            if "bedroom" in label:
                beds = extract_number(label)
            elif "bathroom" in label:
                baths = extract_number(label)
            elif "car space" in label:
                cars = extract_number(label)
            elif "m²" in label or "building size" in label:
                area = extract_number(label)

        # Property type
        try:
            raw_type = card.find_element(By.CSS_SELECTOR, "ul.residential-card__primary p").text
            prop_type = normalize_type(raw_type)
        except:
            prop_type = ""

        return address, full_link, beds, baths, cars, area, prop_type, asking_price
    except Exception as e:
        print(f"❌ Error parsing card: {e}")
        return None

def scrape_suburb(driver, suburb, writer, existing, scrape_date, pages):
    suburb_encoded = quote_plus(suburb.lower())
    base_url = f"https://www.realestate.com.au/buy/property-house-townhouse-unit+apartment-villa-between-0-550000-in-{suburb_encoded},+wa/list-{{}}?misc=ex-under-contract&source=refinement"

    for page in range(1, pages + 1):
        url = base_url.format(page)
        cards = scrape_page(driver, url)
        print(f"🔍 Found {len(cards)} listings on page {page} for suburb '{suburb}'")

        for card in cards:
            result = extract_listing(card)
            if not result:
                continue

            address, full_link, beds, baths, cars, area, prop_type, asking_price = result

            if full_link in existing:
                first_date = existing[full_link]["Scraped Date"]
                try:
                    days_on_market = (date.today() - datetime.strptime(first_date, "%Y-%m-%d").date()).days
                except:
                    days_on_market = ""
            else:
                days_on_market = ""

            writer.writerow([
                address, full_link, beds, baths, cars, area,
                prop_type, suburb, scrape_date, days_on_market, asking_price
            ])

        print(f"✅ Page {page} scraped for '{suburb}'")

def main():
    parser = argparse.ArgumentParser(description="Scrape multiple Perth suburbs into one CSV")
    parser.add_argument("--suburbs", nargs="+", required=True, help="List of suburbs to scrape")
    parser.add_argument("--pages", type=int, default=3, help="Number of pages per suburb")
    parser.add_argument("--output", type=str, default="all_perth.csv", help="Output CSV filename")
    args = parser.parse_args()

    scrape_date = date.today().isoformat()
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    driver = uc.Chrome(options=options, headless=False)

    existing = load_existing(args.output)

    with open(args.output, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        if not existing:
            writer.writerow([
                "Address", "Link", "Bedrooms", "Bathrooms", "Parking", "Area",
                "Type", "Suburb", "Scraped Date", "Days on Market", "Asking Price"
            ])

        for suburb in args.suburbs:
            scrape_suburb(driver, suburb, writer, existing, scrape_date, args.pages)

    driver.quit()
    print(f"📄 Scraping complete. Data saved to {args.output}")

if __name__ == "__main__":
    main()