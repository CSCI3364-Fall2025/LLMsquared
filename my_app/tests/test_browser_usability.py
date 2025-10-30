import os
import time
import pytest

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# ---------- Helpers to create drivers per browser ----------
def _make_driver(browser_name: str):
    browser_name = browser_name.lower()
    try:
        if browser_name == "google" or browser_name == "chrome":
            opts = webdriver.ChromeOptions()
            if os.environ.get("HEADLESS", "1") == "1":
                opts.add_argument("--headless=new")
            return webdriver.Chrome(options=opts)

        if browser_name == "mozilla" or browser_name == "firefox":
            opts = webdriver.FirefoxOptions()
            if os.environ.get("HEADLESS", "1") == "1":
                opts.add_argument("--headless")
            return webdriver.Firefox(options=opts)

        if browser_name == "safari":
            # Safari WebDriver is only available on macOS with "Allow Remote Automation" enabled
            return webdriver.Safari()

    except Exception:
        # If driver missing, skip that browser gracefully
        return None

    raise ValueError(f"Unsupported browser: {browser_name}")

# ---------- Pytest config ----------
# Browsers to test
BROWSERS = ["google", "mozilla", "safari"]

@pytest.fixture(params=BROWSERS, scope="class")
def browser_name(request):
    return request.param

@pytest.fixture(scope="class")
def driver(browser_name):
    drv = _make_driver(browser_name)
    if drv is None:
        pytest.skip(f"WebDriver for {browser_name} not available or not configured.")
    yield drv
    drv.quit()

# Django DB mark
pytestmark = pytest.mark.django_db

# ---------- Example selectors ----------
HOME_PATH = "/"
NAV_LINK_SELECTOR = "a[href='/']"
FORM_INPUT_SELECTOR = "input[name='q']"
FORM_SUBMIT_SELECTOR = "button[type='submit']"
SUCCESS_MARKER_SELECTOR = "[data-test='ok']"

# ---------- Tests ----------
class TestBrowserUsability:
    def test_homepage_loads_and_has_title(self, live_server, driver, browser_name):
        url = live_server.url + HOME_PATH
        driver.get(url)
        assert driver.title is not None and driver.title != ""

    def test_layout_is_responsive_basic(self, live_server, driver, browser_name):
        url = live_server.url + HOME_PATH
        driver.get(url)
        driver.set_window_size(1366, 800)
        time.sleep(0.2)
        width_desktop = driver.execute_script("return document.body.clientWidth;")

        driver.set_window_size(375, 812)
        time.sleep(0.2)
        width_mobile = driver.execute_script("return document.body.clientWidth;")
        assert width_desktop != width_mobile

    def test_key_navigation_and_focus(self, live_server, driver, browser_name):
        url = live_server.url + HOME_PATH
        driver.get(url)
        body = driver.find_element(By.TAG_NAME, "body")
        start_active = driver.switch_to.active_element
        body.send_keys(Keys.TAB)
        time.sleep(0.1)
        after_tab = driver.switch_to.active_element
        assert start_active != after_tab

    def test_form_submit_smoke(self, live_server, driver, browser_name):
        url = live_server.url + HOME_PATH
        driver.get(url)
        inputs = driver.find_elements(By.CSS_SELECTOR, FORM_INPUT_SELECTOR)
        submits = driver.find_elements(By.CSS_SELECTOR, FORM_SUBMIT_SELECTOR)
        if not inputs or not submits:
            pytest.skip("Form selectors not present on this page")
        inputs[0].clear()
        inputs[0].send_keys("test")
        submits[0].click()
        time.sleep(0.3)
        ok = driver.find_elements(By.CSS_SELECTOR, SUCCESS_MARKER_SELECTOR)
        assert ok, "Expected success marker after form submit"

    def test_no_obvious_js_errors_on_load(self, live_server, driver, browser_name):
        driver.get(live_server.url + HOME_PATH)
        driver.execute_script(
            """
            window.__errors = [];
            window.addEventListener('error', function(e){ window.__errors.push(e.message || 'error'); });
            """
        )
        driver.get(live_server.url + HOME_PATH)
        time.sleep(0.2)
        errors = driver.execute_script("return window.__errors;") or []
        assert all("ReferenceError" not in e for e in errors), f"JS errors: {errors}"
