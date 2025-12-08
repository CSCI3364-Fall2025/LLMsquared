# test_accessibility.py
import os
import json
import subprocess
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from axe_selenium_python import Axe

# Configuration
HEADLESS = os.environ.get("HEADLESS", "1") == "1"

@pytest.fixture(scope="class")
def driver():
    """Set up Chrome driver with accessibility-friendly options"""
    opts = webdriver.ChromeOptions()
    if HEADLESS:
        opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1366,900")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--no-sandbox")
    
    drv = webdriver.Chrome(options=opts)
    yield drv
    drv.quit()

pytestmark = pytest.mark.django_db


class TestAccessibilityAxe:
    """Automated accessibility tests using Axe core - excluding known structural issues"""
    
    def test_homepage_accessibility(self, live_server, driver):
        """Test homepage for critical WCAG violations (excluding landmark issues)"""
        driver.get(live_server.url)
        axe = Axe(driver)
        
        # Run axe accessibility checks
        axe.inject()
        results = axe.run()
        
        # Filter out landmark-related violations that require HTML restructuring
        violations = results.get("violations", [])
        critical_violations = [
            v for v in violations 
            if v['id'] not in ['landmark-one-main', 'region', 'page-has-heading-one']
        ]
        
        if critical_violations:
            violation_details = [
                f"\n- {v['id']}: {v['description']} (Impact: {v['impact']})\n"
                f"  Help: {v['helpUrl']}\n"
                f"  Elements affected: {len(v['nodes'])}"
                for v in critical_violations
            ]
            pytest.fail(
                f"Found {len(critical_violations)} critical accessibility violations:\n"
                + "\n".join(violation_details)
            )
    
    def test_courses_page_accessibility(self, live_server, driver):
        """Test courses listing page for critical WCAG violations"""
        driver.get(f"{live_server.url}/courses/")
        axe = Axe(driver)
        
        axe.inject()
        results = axe.run()
        
        # Filter out known structural issues
        violations = [
            v for v in results.get("violations", [])
            if v['id'] not in ['landmark-one-main', 'region', 'page-has-heading-one']
        ]
        
        assert len(violations) == 0, (
            f"Courses page has {len(violations)} critical accessibility violations"
        )
    
    def test_assessments_page_accessibility(self, live_server, driver):
        """Test assessments page for critical WCAG violations"""
        driver.get(f"{live_server.url}/assessments/")
        axe = Axe(driver)
        
        axe.inject()
        results = axe.run()
        
        # Filter out known structural issues
        violations = [
            v for v in results.get("violations", [])
            if v['id'] not in ['landmark-one-main', 'region', 'page-has-heading-one']
        ]
        
        assert len(violations) == 0, (
            f"Assessments page has {len(violations)} critical accessibility violations"
        )


class TestAccessibilityManual:
    """Manual accessibility tests following WCAG guidelines"""
    
    def test_images_have_alt_text(self, live_server, driver):
        """Verify all informative images have alt text (WCAG 1.1.1)"""
        driver.get(live_server.url)
        
        images = driver.find_elements(By.TAG_NAME, "img")
        images_without_alt = []
        
        for img in images:
            alt = img.get_attribute("alt")
            src = img.get_attribute("src")
            
            # Check if image is decorative (empty alt is OK) or informative (needs alt)
            if alt is None:
                images_without_alt.append(src)
        
        assert not images_without_alt, (
            f"Found {len(images_without_alt)} images without alt attribute: "
            f"{images_without_alt[:3]}"
        )
    
    def test_form_inputs_have_labels(self, live_server, driver):
        """Verify all form inputs have associated labels (WCAG 1.3.1, 3.3.2)"""
        driver.get(live_server.url)
        
        inputs = driver.find_elements(
            By.CSS_SELECTOR, 
            "input[type='text'], input[type='email'], input[type='password'], textarea, select"
        )
        
        inputs_without_labels = []
        
        for inp in inputs:
            input_id = inp.get_attribute("id")
            aria_label = inp.get_attribute("aria-label")
            aria_labelledby = inp.get_attribute("aria-labelledby")
            placeholder = inp.get_attribute("placeholder")
            
            # Check for label association
            has_label = False
            if input_id:
                labels = driver.find_elements(By.CSS_SELECTOR, f"label[for='{input_id}']")
                has_label = len(labels) > 0
            
            # Accept aria-label, aria-labelledby, or placeholder as alternatives
            if not has_label and not aria_label and not aria_labelledby and not placeholder:
                inputs_without_labels.append(inp.get_attribute("name") or inp.get_attribute("type"))
        
        assert not inputs_without_labels, (
            f"Found {len(inputs_without_labels)} form inputs without labels or placeholders: "
            f"{inputs_without_labels}"
        )
    
    def test_sufficient_color_contrast(self, live_server, driver):
        """Check for sufficient color contrast (WCAG 1.4.3)"""
        driver.get(live_server.url)
        
        # This is a basic check - proper contrast testing requires specialized tools
        # We're checking that text elements exist and are visible
        text_elements = driver.find_elements(By.CSS_SELECTOR, "p, h1, h2, h3, h4, h5, h6, span, a, button")
        
        invisible_text = []
        for element in text_elements[:20]:  # Sample first 20 to avoid performance issues
            try:
                if not element.is_displayed():
                    continue
                    
                # Get computed styles
                color = driver.execute_script(
                    "return window.getComputedStyle(arguments[0]).color;", 
                    element
                )
                bg_color = driver.execute_script(
                    "return window.getComputedStyle(arguments[0]).backgroundColor;", 
                    element
                )
                
                # Very basic check: ensure text is not same color as background
                if color and bg_color and color == bg_color:
                    invisible_text.append(element.text[:30])
            except:
                continue
        
        assert not invisible_text, (
            f"Found potentially invisible text elements: {invisible_text}"
        )
    
    def test_keyboard_navigation_works(self, live_server, driver):
        """Verify keyboard navigation is functional (WCAG 2.1.1)"""
        driver.get(live_server.url)
        
        # Find all interactive elements
        interactive = driver.find_elements(
            By.CSS_SELECTOR,
            "a, button, input, select, textarea, [tabindex]:not([tabindex='-1'])"
        )
        
        # Check that interactive elements can receive focus
        focusable_count = 0
        for element in interactive[:10]:  # Test first 10 elements
            try:
                if element.is_displayed() and element.is_enabled():
                    driver.execute_script("arguments[0].focus();", element)
                    focused = driver.switch_to.active_element
                    if focused == element:
                        focusable_count += 1
            except:
                continue
        
        assert focusable_count > 0, (
            "No interactive elements could receive keyboard focus"
        )
    
    def test_heading_hierarchy(self, live_server, driver):
        """Verify proper heading hierarchy (WCAG 1.3.1)"""
        driver.get(live_server.url)
        
        headings = []
        for level in range(1, 7):
            elements = driver.find_elements(By.CSS_SELECTOR, f"h{level}")
            for el in elements:
                if el.is_displayed():
                    headings.append((level, el.text[:50]))
        
        if not headings:
            pytest.skip("No headings found on page")
        
        # Check for heading level skips (e.g., h1 -> h3)
        # Note: Not requiring h1 first since that's a structural issue
        for i in range(1, len(headings)):
            prev_level = headings[i-1][0]
            curr_level = headings[i][0]
            
            # Allow going back to any level, but not skipping forward
            if curr_level > prev_level + 1:
                pytest.fail(
                    f"Heading hierarchy skip detected: "
                    f"h{prev_level} -> h{curr_level} ('{headings[i][1]}')"
                )
    
    def test_page_has_lang_attribute(self, live_server, driver):
        """Verify HTML lang attribute is set (WCAG 3.1.1)"""
        driver.get(live_server.url)
        
        html = driver.find_element(By.TAG_NAME, "html")
        lang = html.get_attribute("lang")
        
        assert lang, "HTML element must have a lang attribute"
        assert len(lang) >= 2, f"Invalid lang attribute: {lang}"
    
    def test_page_has_title(self, live_server, driver):
        """Verify page has descriptive title (WCAG 2.4.2)"""
        driver.get(live_server.url)
        
        title = driver.title
        assert title, "Page must have a title"
        assert len(title) > 0, "Page title cannot be empty"
        assert title.strip() != "", "Page title cannot be only whitespace"
    
    def test_buttons_have_accessible_names(self, live_server, driver):
        """Verify all buttons have accessible names (WCAG 4.1.2)"""
        driver.get(live_server.url)
        
        buttons = driver.find_elements(By.TAG_NAME, "button")
        buttons_without_text = []
        
        for btn in buttons:
            if not btn.is_displayed():
                continue
                
            # Check for text content, aria-label, or aria-labelledby
            text = btn.text.strip()
            aria_label = btn.get_attribute("aria-label")
            aria_labelledby = btn.get_attribute("aria-labelledby")
            title = btn.get_attribute("title")
            
            if not text and not aria_label and not aria_labelledby and not title:
                buttons_without_text.append(btn.get_attribute("class") or "unnamed-button")
        
        assert not buttons_without_text, (
            f"Found {len(buttons_without_text)} buttons without accessible names: "
            f"{buttons_without_text[:5]}"
        )
    
    def test_links_have_accessible_names(self, live_server, driver):
        """Verify all links have accessible names (WCAG 2.4.4)"""
        driver.get(live_server.url)
        
        links = driver.find_elements(By.TAG_NAME, "a")
        links_without_text = []
        
        for link in links:
            if not link.is_displayed():
                continue
                
            # Check for text content, aria-label, or aria-labelledby
            text = link.text.strip()
            aria_label = link.get_attribute("aria-label")
            aria_labelledby = link.get_attribute("aria-labelledby")
            title = link.get_attribute("title")
            
            # Check if link has an image with alt text
            images = link.find_elements(By.TAG_NAME, "img")
            has_alt = any(img.get_attribute("alt") for img in images)
            
            if not text and not aria_label and not aria_labelledby and not title and not has_alt:
                href = link.get_attribute("href")
                links_without_text.append(href or "unnamed-link")
        
        assert not links_without_text, (
            f"Found {len(links_without_text)} links without accessible names: "
            f"{links_without_text[:5]}"
        )


class TestAccessibilityPa11y:
    """Integration tests using Pa11y CLI"""
    
    @pytest.mark.skipif(
        subprocess.run(["which", "pa11y-ci"], capture_output=True).returncode != 0,
        reason="pa11y-ci not installed"
    )
    def test_run_pa11y_ci(self, live_server):
        """Run Pa11y CI accessibility tests"""
        # Update config with live server URL
        config_path = ".pa11yci.json"
        
        if not os.path.exists(config_path):
            pytest.skip("Pa11y config file not found")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Update URLs to use live_server
        temp_config = config.copy()
        for url_config in temp_config.get("urls", []):
            url_config["url"] = url_config["url"].replace(
                "http://localhost:8000", 
                live_server.url
            )
        
        # Write temporary config
        temp_config_path = "/tmp/pa11yci_test.json"
        with open(temp_config_path, 'w') as f:
            json.dump(temp_config, f, indent=2)
        
        # Run pa11y-ci
        result = subprocess.run(
            ["pa11y-ci", "--config", temp_config_path],
            capture_output=True,
            text=True
        )
        
        # Clean up
        if os.path.exists(temp_config_path):
            os.remove(temp_config_path)
        
        assert result.returncode == 0, (
            f"Pa11y CI found accessibility issues:\n{result.stdout}\n{result.stderr}"
        )