"""Naukri DOM fixtures: login detection and SRP card selectors (no live site)."""

from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from automation.sources import naukri

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "naukri"


@pytest.fixture
def chrome_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)
    yield driver
    driver.quit()


def test_is_logged_in_matches_header_fixture(chrome_driver):
    path = (FIXTURES / "01_logged_in_header.html").as_uri()
    chrome_driver.get(path)
    assert naukri.is_logged_in(chrome_driver) is True


def test_srp_card_css_finds_tuples(chrome_driver):
    from selenium.webdriver.common.by import By

    path = (FIXTURES / "02_srp_job_card.html").as_uri()
    chrome_driver.get(path)
    cards = chrome_driver.find_elements(By.CSS_SELECTOR, naukri._CARD_CSS.split(",")[0].strip())
    assert len(cards) >= 1
    wrapper_cards = chrome_driver.find_elements(
        By.CSS_SELECTOR, "div.srp-jobtuple-wrapper, article.jobTuple, div.cust-job-tuple"
    )
    assert len(wrapper_cards) == 2
