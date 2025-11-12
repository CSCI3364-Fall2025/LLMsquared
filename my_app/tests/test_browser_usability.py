# test_browser_usability.py
import os
import time
import pytest

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from playwright.sync_api import sync_playwright

# Selenium driver setup
def _make_driver(browser_name: str):
    browser_name = browser_name.lower()
    try:
        if browser_name in ("google", "chrome"):
            opts = webdriver.ChromeOptions()
            if os.environ.get("HEADLESS", "1") == "1":
                opts.add_argument("--headless=new")
                opts.add_argument("--window-size=1366,900")
            return webdriver.Chrome(options=opts)

        if browser_name in ("mozilla", "firefox"):
            opts = webdriver.FirefoxOptions()
            if os.environ.get("HEADLESS", "1") == "1":
                opts.add_argument("--headless")
            return webdriver.Firefox(options=opts)

        # Safari covered by Playwright below
        if browser_name == "safari":
            return None

    except Exception:
        # If driver missing, skip
        return None

    raise ValueError(f"Unsupported browser: {browser_name}")

SELENIUM_BROWSERS = ["google", "mozilla"]

@pytest.fixture(params=SELENIUM_BROWSERS, scope="class")
def selenium_browser(request):
    return request.param

@pytest.fixture(scope="class")
def driver(selenium_browser):
    drv = _make_driver(selenium_browser)
    if drv is None:
        pytest.skip(f"WebDriver for {selenium_browser} not available or not configured.")
    yield drv
    drv.quit()

pytestmark = pytest.mark.django_db

HOME_PATH = "/"
FORM_INPUT_SELECTOR = "input[name='q']"
FORM_SUBMIT_SELECTOR = "button[type='submit']"
SUCCESS_MARKER_SELECTOR = "[data-test='ok']"

LEVEL_NAV_THRESHOLDS_MS = {
    "L1": 4000,
    "L2": 7000,
    "L3": 12000,
}

@pytest.fixture(scope="class")
def level_name():
    return os.environ.get("TEST_LEVEL_NAME", "L1")

@pytest.fixture(scope="class")
def level_config(level_name):
    return {
        "name": level_name,
        "nav_threshold_ms": LEVEL_NAV_THRESHOLDS_MS.get(level_name, 7000),
    }

# Tests 
class TestBrowserUsability:
    def test_homepage_loads_and_has_title(self, live_server, driver, level_config):
        url = live_server.url + HOME_PATH
        driver.get(url)
        assert driver.title is not None and driver.title != ""

    def test_layout_is_responsive_basic(self, live_server, driver, level_config):
        url = live_server.url + HOME_PATH
        driver.get(url)
        driver.set_window_size(1366, 800)
        time.sleep(0.2)
        width_desktop = driver.execute_script("return document.body.clientWidth;")

        driver.set_window_size(375, 812)
        time.sleep(0.2)
        width_mobile = driver.execute_script("return document.body.clientWidth;")
        assert width_desktop != width_mobile

    def test_key_navigation_and_focus(self, live_server, driver, level_config):
        url = live_server.url + HOME_PATH
        driver.get(url)
        body = driver.find_element(By.TAG_NAME, "body")
        start_active = driver.switch_to.active_element
        body.send_keys(Keys.TAB)
        time.sleep(0.1)
        after_tab = driver.switch_to.active_element
        assert start_active != after_tab

    def test_form_submit_smoke(self, live_server, driver, level_config):
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

    def test_no_obvious_js_errors_on_load(self, live_server, driver, level_config):
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

    def test_navigation_perf_is_reasonable_for_level(self, live_server, driver, level_config):
        """
        Uses PerformanceNavigationTiming if available; falls back to Navigation Timing.
        This doesn't replace real perf testing, but it flags obvious regressions as data scales.
        """
        driver.get(live_server.url + HOME_PATH)
        time.sleep(0.2)

        nav_entry = driver.execute_script(
            """
            var e = (performance.getEntriesByType && performance.getEntriesByType('navigation')) || [];
            if (e && e.length) {
                var n = e[0];
                return {
                    dcl: n.domContentLoadedEventEnd, // ms from startTime(=0) for nav entries
                    start: n.startTime
                };
            }
            return null;
            """
        )

        if nav_entry and "dcl" in nav_entry and nav_entry["dcl"]:
            dcl_ms = float(nav_entry["dcl"])
        else:
            timing = driver.execute_script("return window.performance && performance.timing ? performance.timing : null;")
            if not timing:
                pytest.skip("No performance timing API available in this browser.")
            dcl_ms = float(timing.get("domContentLoadedEventEnd", 0) - timing.get("navigationStart", 0))

        threshold = level_config["nav_threshold_ms"]
        assert dcl_ms <= threshold, f"[{level_config['name']}] DOMContentLoaded {dcl_ms:.0f}ms > {threshold}ms"

# Playwright Safari (WebKit) Tests
HEADLESS = os.getenv("PW_HEADLESS", "1") == "1"   
@pytest.mark.usefixtures("live_server")
class TestSafariPlaywright:
    def test_safari_homepage_loads(self, live_server):
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=HEADLESS)
            page = browser.new_page()
            page.goto(live_server.url)
            assert page.title(), "Safari/WebKit should have a non-empty title"
            browser.close()

    def test_safari_layout_responsive(self, live_server):
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=HEADLESS)
            page = browser.new_page()
            page.goto(live_server.url)
            desktop_width = page.evaluate("document.body.clientWidth")
            page.set_viewport_size({"width": 375, "height": 812})
            mobile_width = page.evaluate("document.body.clientWidth")
            assert desktop_width != mobile_width
            browser.close()

    def test_safari_js_no_errors(self, live_server):
        with sync_playwright() as p:
            browser = p.webkit.launch(headless=HEADLESS)
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(live_server.url)
            page.wait_for_load_state("domcontentloaded")
            assert not errors, f"JS errors: {errors}"
            browser.close()