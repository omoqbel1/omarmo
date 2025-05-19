import logging
import sys
import argparse
import time
import requests
import json
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Initial logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# File handler only, no console handler to avoid stdout pollution
try:
    file_handler = logging.FileHandler('fmcsa_scraper.log')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    logger.info("Logging setup completed successfully")
except Exception as e:
    logger.error(f"Failed to setup file logging: {str(e)}")

logger.info("Script started")

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    logger.info("Selenium dependencies imported successfully")
except ImportError as e:
    logger.error(f"Failed to import Selenium dependencies: {str(e)}")
    sys.exit(1)

def solve_recaptcha_with_2captcha(api_key, site_key, url):
    """
    Solve reCAPTCHA using 2Captcha by sending a request and polling for the solution.
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            in_url = "https://2captcha.com/in.php"
            params = {
                "key": api_key,
                "method": "userrecaptcha",
                "googlekey": site_key,
                "pageurl": url,
                "json": 1
            }
            logger.info("Sending reCAPTCHA solving request to 2Captcha (attempt %d)", attempt + 1)
            response = requests.post(in_url, params=params)
            result = response.json()
            logger.debug(f"2Captcha initial response: {result}")

            if result.get("status") != 1:
                logger.error(f"Failed to submit reCAPTCHA to 2Captcha: {result.get('request')}")
                raise Exception(f"2Captcha submission failed: {result.get('request')}")

            request_id = result.get("request")
            logger.info(f"2Captcha request ID: {request_id}")

            max_wait_time = 120
            start_time = time.time()
            res_url = "https://2captcha.com/res.php"

            while True:
                elapsed_time = time.time() - start_time
                if elapsed_time > max_wait_time:
                    logger.error("2Captcha took too long to solve the reCAPTCHA (waited 2 minutes)")
                    raise Exception("2Captcha timeout after 2 minutes")

                params = {
                    "key": api_key,
                    "action": "get",
                    "id": request_id,
                    "json": 1
                }
                response = requests.get(res_url, params=params)
                result = response.json()
                logger.debug(f"2Captcha polling response after {elapsed_time:.2f} seconds: {result}")

                if result.get("status") == 1:
                    logger.info(f"reCAPTCHA solved successfully by 2Captcha in {elapsed_time:.2f} seconds")
                    return result.get("request")

                if result.get("request") != "CAPCHA_NOT_READY":
                    logger.error(f"2Captcha failed to solve the reCAPTCHA: {result.get('request')}")
                    raise Exception(f"2Captcha solving failed: {result.get('request')}")

                logger.debug("Waiting for 2Captcha to solve the reCAPTCHA...")
                time.sleep(5)
        except Exception as e:
            logger.warning(f"2Captcha attempt %d failed: {str(e)}", attempt + 1)
            if attempt == max_retries - 1:
                logger.error("2Captcha failed after all retries")
                raise Exception("2Captcha failed after all retries")
            time.sleep(10)

def scrape_fmcsa_insurance(mc_number, captcha_api_key):
    """
    Scrape insurance information from FMCSA Licensing & Insurance Carrier Search website.
    """
    logger.info("Initializing Selenium WebDriver in headless mode")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")

    driver = None
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        logger.info("WebDriver initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize WebDriver: {str(e)}")
        return [{"error": f"WebDriver initialization failed: {str(e)}"}]

    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false,
                });
            """
        })

        logger.info("Step 1: Navigating to FMCSA Carrier Search page")
        driver.get("https://li-public.fmcsa.dot.gov/LIVIEW/pkg_carrquery.prc_carrlist")

        logger.info(f"Step 2: Entering MC number: {mc_number}")
        time.sleep(2)
        try:
            docket_input = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.NAME, "n_docketno"))
            )
            docket_input.send_keys(mc_number)
            logger.info(f"MC number {mc_number} entered on the webpage")
        except Exception as e:
            logger.error(f"Failed to enter MC number: {str(e)}")
            logger.debug(f"Page source: {driver.page_source}")
            raise

        logger.info("Step 3: Solving reCAPTCHA with 2Captcha")
        try:
            site_key = driver.find_element(By.CLASS_NAME, "g-recaptcha").get_attribute("data-sitekey")
            logger.info(f"reCAPTCHA site key: {site_key}")
            url = driver.current_url
            captcha_solution = solve_recaptcha_with_2captcha(captcha_api_key, site_key, url)
            driver.execute_cdp_cmd('Runtime.evaluate', {
                'expression': f'document.getElementById("g-recaptcha-response").innerHTML="{captcha_solution}";'
            })
            callback = driver.find_element(By.CLASS_NAME, "g-recaptcha").get_attribute("data-callback")
            if callback:
                driver.execute_cdp_cmd('Runtime.evaluate', {
                    'expression': f"{callback}('{captcha_solution}');"
                })
            else:
                logger.warning("No reCAPTCHA callback function found. Proceeding without callback.")
            time.sleep(2)
            recaptcha_response = driver.find_element(By.NAME, "g-recaptcha-response").get_attribute("value")
            if not recaptcha_response:
                logger.error("reCAPTCHA verification failed after 2Captcha solution.")
                raise Exception("reCAPTCHA verification failed after 2Captcha solution")
        except Exception as e:
            logger.error(f"reCAPTCHA solving error: {str(e)}")
            logger.debug(f"Page source: {driver.page_source}")
            raise

        logger.info("Step 4: Clicking Search button")
        try:
            search_button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@type='submit' and @value='   Search   ']"))
            )
            search_button.click()
        except Exception as e:
            logger.error(f"Failed to click Search button: {str(e)}")
            logger.debug(f"Page source: {driver.page_source}")
            raise

        logger.info("Step 5: Clicking HTML button")
        time.sleep(2)
        try:
            html_button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@type='submit' and @value='HTML']"))
            )
            html_button.click()
        except Exception as e:
            logger.error(f"Failed to click HTML button: {str(e)}")
            logger.debug(f"Page source: {driver.page_source}")
            raise

        logger.info("Step 6: Clicking Active/Pending Insurance link")
        time.sleep(2)
        try:
            active_insurance_form = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//form[contains(@action, 'prc_activeinsurance')]"))
            )
            driver.execute_script("arguments[0].submit();", active_insurance_form)
        except Exception as e:
            logger.error(f"Failed to click Active/Pending Insurance link: {str(e)}")
            logger.debug(f"Page source: {driver.page_source}")
            raise

        logger.info("Step 7: Waiting for insurance page to load")
        try:
            # Wait for the insurance table or an indication of data
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
            # Wait longer for dynamic content
            time.sleep(5)
        except Exception as e:
            logger.error(f"Failed to load insurance page: {str(e)}")
            logger.debug(f"Page source: {driver.page_source}")
            raise

        logger.info("Step 8: Parsing insurance page")
        try:
            soup = BeautifulSoup(driver.page_source, "html.parser")
            # Check for no data message
            no_data_message = soup.find("strong", string="No Data Available")
            if no_data_message:
                logger.info("No insurance data available for MC number %s", mc_number)
                return [{
                    "type": "No Insurance on file",
                    "policy_surety_number": "No Insurance on file",
                    "posted_date": "",
                    "coverage_from": "",
                    "coverage_to": "",
                    "effective_date": "",
                    "cancellation_date": ""
                }]

            insurance_data = []
            tables = soup.find_all("table")
            if not tables:
                logger.error("No tables found on insurance page")
                logger.debug(f"Page source: {driver.page_source}")
                return [{"error": "No tables found on insurance page"}]

            target_table = None
            for table in tables:
                headers = [th.text.strip().lower() for th in table.find_all("th")]
                if "insurance carrier" in headers:
                    target_table = table
                    break

            if not target_table:
                logger.error("No table with 'Insurance Carrier' header found")
                logger.debug(f"Page source: {driver.page_source}")
                return [{"error": "No table with 'Insurance Carrier' header found"}]

            # Log the raw table data for debugging
            rows = target_table.find_all("tr")
            if not rows:
                logger.error("No rows found in insurance table")
                logger.debug(f"Page source: {driver.page_source}")
                return [{"error": "No rows found in insurance table"}]

            # Log the headers to understand the table structure
            headers = [th.text.strip() for th in rows[0].find_all("th")]
            logger.info(f"Table headers: {headers}")

            # Expanded list of valid insurance types
            valid_insurance_types = {
                "BIPD/Primary", "BIPD/Excess", "Cargo", "General Liability",
                "Auto Liability", "Workers Comp", "Surety Bond", "Trust Fund",
                "Excess BIPD", "Primary BIPD", "SURETY"
            }

            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                logger.info(f"Raw row cells: {[cell.text.strip() for cell in cells]}")

                # Dynamically map cells based on header positions
                if len(cells) < len(headers):
                    logger.debug(f"Skipping row with insufficient cells: {len(cells)} (expected at least {len(headers)})")
                    continue

                # Map cells to fields based on header positions
                cell_data = {headers[i].lower(): cells[i].text.strip() for i in range(len(headers))}

                insurance_type = cell_data.get('type', '')  # Match header 'Type'
                # Normalize insurance type for matching by removing spaces, slashes, and converting to lowercase
                normalized_insurance_type = insurance_type.replace(" ", "").replace("/", "").lower()
                # Normalize valid types for comparison
                matched_type = next((valid_type for valid_type in valid_insurance_types if normalized_insurance_type == valid_type.replace(" ", "").replace("/", "").lower()), None)
                if not matched_type:
                    logger.debug(f"Discarding insurance type: '{insurance_type}' (normalized: '{normalized_insurance_type}')")
                    continue

                entry = {
                    "type": insurance_type,  # Keep original type for output
                    "insurance_carrier": cell_data.get('insurance carrier', ''),
                    "policy_surety_number": cell_data.get('policy/surety', ''),
                    "posted_date": cell_data.get('posted  date', ''),  # Match header 'Posted  Date'
                    "coverage_from": cell_data.get('coverage from', ''),
                    "coverage_to": cell_data.get('coverage to', ''),
                    "effective_date": cell_data.get('effective  date', ''),  # Match header 'Effective  Date'
                    "cancellation_date": cell_data.get('cancellation  date', '')
                }
                logger.info(f"Parsed insurance entry: {json.dumps(entry, indent=2)}")
                insurance_data.append(entry)

            if not insurance_data:
                logger.info("No qualifying insurance data extracted for MC number %s", mc_number)
                logger.debug(f"Page source: {driver.page_source}")
                return [{
                    "type": "No Insurance on file",
                    "policy_surety_number": "No Insurance on file",
                    "posted_date": "",
                    "coverage_from": "",
                    "coverage_to": "",
                    "effective_date": "",
                    "cancellation_date": ""
                }]

            logger.info("Successfully processed insurance details")
            return insurance_data
        except Exception as e:
            logger.error(f"Failed to parse insurance page: {str(e)}")
            logger.debug(f"Page source: {driver.page_source}")
            raise

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.debug(f"Page source: {driver.page_source if driver else 'Driver not initialized'}")
        return [{"error": f"Unexpected error: {str(e)}"}]

    finally:
        if driver:
            driver.quit()

def main():
    try:
        logger.info("Parsing command-line arguments")
        parser = argparse.ArgumentParser(description="Scrape FMCSA insurance details for a given MC number.")
        parser.add_argument("mc_number", help="The MC number to search (e.g., 1060228)")
        args = parser.parse_args()
        mc_number = args.mc_number
        logger.info(f"MC number provided: {mc_number}")
        captcha_api_key = "4600bf5acc830e9b36a4a6580d2e3b58"
        logger.info(f"Starting scrape for MC number: {mc_number}")
        result = scrape_fmcsa_insurance(mc_number, captcha_api_key)
        print(json.dumps(result, indent=2))
        return result
    except Exception as e:
        logger.error(f"Failed to scrape insurance details: {str(e)}")
        print(json.dumps({"error": str(e)}, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()
