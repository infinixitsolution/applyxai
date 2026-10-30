"""LinkedIn profile sync fixture smoke (selectors present in saved HTML)."""

from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "linkedin_profile"


@pytest.fixture
def chrome_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()


def test_headline_edit_controls_in_fixture(chrome_driver):
    path = (FIXTURES / "01_headline_edit.html").as_uri()
    chrome_driver.get(path)
    assert chrome_driver.find_elements(By.CSS_SELECTOR, "#top-card-text-edit-button")
    assert chrome_driver.find_elements(
        By.CSS_SELECTOR, "input[id*='headline'], input[name='headline']"
    )
