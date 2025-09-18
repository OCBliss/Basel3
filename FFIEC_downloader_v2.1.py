from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import time
import os


def get_ffiec_date_dropdown_map():
    url = "https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx"

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_experimental_option("prefs", {
        "download.prompt_for_download": False,
        "safebrowsing.enabled": True
    })

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)
    driver.get(url)

    try:
        # Step 1: Select report type
        report_type_dropdown = wait.until(EC.presence_of_element_located((By.ID, "ListBox1")))
        Select(report_type_dropdown).select_by_value("ReportingSeriesSinglePeriod")

        # Step 2: Wait for date dropdown to populate
        date_dropdown = wait.until(EC.presence_of_element_located((By.ID, "DatesDropDownList")))
        select = Select(date_dropdown)

        date_map = {}
        for option in select.options:
            label = option.text.strip()
            value = option.get_attribute("value")
            if label and value.isdigit():
                date_map[label] = value

        return date_map

    finally:
        driver.quit()


def get_latest_quarter_label():
    today = datetime.today()
    y, m, d = today.year, today.month, today.day

    if m == 1 and d >= 31:
        return f"12/31/{y - 1}"
    elif m == 4 and d >= 30:
        return f"03/31/{y}"
    elif m == 7 and d >= 31:
        return f"06/30/{y}"
    elif m == 10 and d >= 31:
        return f"09/30/{y}"
    else:
        return None


def download_ffiec_call_report(date_value, download_dir="downloads"):
    os.makedirs(download_dir, exist_ok=True)
    url = "https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx"

    options = webdriver.ChromeOptions()
    # Uncomment for silent headless download
    # options.add_argument("--headless=new")
    options.add_experimental_option("prefs", {
        "download.default_directory": os.path.abspath(download_dir),
        "download.prompt_for_download": False,
        "directory_upgrade": True,
        "safebrowsing.enabled": True
    })

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)
    driver.get(url)

    try:
        report_type_dropdown = wait.until(EC.presence_of_element_located((By.ID, "ListBox1")))
        Select(report_type_dropdown).select_by_value("ReportingSeriesSinglePeriod")
        print("✔️ Selected report type.")

        date_dropdown = wait.until(EC.presence_of_element_located((By.ID, "DatesDropDownList")))
        Select(date_dropdown).select_by_value(date_value)
        print("✔️ Selected report date.")

        tab_radio = wait.until(EC.element_to_be_clickable((By.ID, "TSVRadioButton")))
        tab_radio.click()
        print("✔️ Selected tab-delimited format.")

        download_button = wait.until(EC.element_to_be_clickable((By.ID, "Download_0")))
        download_button.click()
        print("⬇️ Download triggered...")

        time.sleep(30)  # Adjust this wait time if needed
        print(f"✅ File saved in: {os.path.abspath(download_dir)}")

    finally:
        driver.quit()


if __name__ == "__main__":
    # label = get_latest_quarter_label()
    label = "06/30/2025"
    if not label:
        print("⏳ Not a scheduled run day. Skipping download.")
    else:
        print(f"🗓️ Target Report Date: {label}")
        date_map = get_ffiec_date_dropdown_map()
        date_value = date_map.get(label)
        if date_value:
            download_ffiec_call_report(date_value=date_value, download_dir="downloads")
        else:
            print(f"❌ No dropdown match for: {label}")
