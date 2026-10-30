"""Best-effort LinkedIn profile edit interactions (Master Profile → linkedin.com/in/me)."""

from __future__ import annotations

import time
from pathlib import Path

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from modules.helpers import human_type, logger


def _open_self_profile(driver) -> None:
    driver.get("https://www.linkedin.com/in/me/")
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "main")))


def _save_modal(driver, timeout: float = 12) -> bool:
    for xpath in (
        "//div[contains(@class,'artdeco-modal')]//button[@aria-label='Save' or normalize-space(.)='Save']",
        "//button[@data-test-modal-save-btn]",
        "//button[contains(@class,'artdeco-button--primary') and normalize-space(.)='Save']",
    ):
        try:
            btn = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            btn.click()
            time.sleep(0.8)
            return True
        except TimeoutException:
            continue
    return False


def _field_text(el) -> str:
    try:
        return (el.get_attribute("value") or el.text or "").strip()
    except Exception:
        return ""


def _should_write(current: str, new: str, *, fill_empty: bool, overwrite: bool) -> bool:
    if not new.strip():
        return False
    if overwrite:
        return True
    if fill_empty:
        return not current.strip()
    return current.strip() != new.strip()


def _fill_input(el, text: str) -> None:
    el.click()
    el.send_keys(Keys.CONTROL, "a")
    human_type(el, text)


def _fill_textarea(el, text: str) -> None:
    el.click()
    el.clear()
    human_type(el, text)


def apply_section(
    driver,
    section: str,
    snapshot: dict,
    settings: dict,
    *,
    photo_path: str = "",
) -> str:
    """Try to apply one section. Returns updated | skipped | failed."""
    known = {"headline", "about", "location", "industry", "skills", "photo", "experience", "education"}
    if section not in known:
        return "skipped"
    if section == "photo":
        path = (photo_path or "").strip()
        if not path or not snapshot.get("has_photo") or not Path(path).is_file():
            return "skipped"
    overwrite = set(settings.get("overwrite_sections") or [])
    fill_empty = bool(settings.get("fill_empty_only", True))
    ow = section in overwrite
    _open_self_profile(driver)

    if section == "headline":
        return _headline(driver, snapshot.get("headline") or "", fill_empty, ow)
    if section == "about":
        return _about(driver, snapshot.get("about") or "", fill_empty, ow)
    if section == "location":
        return _location(driver, snapshot.get("location") or "", fill_empty, ow)
    if section == "industry":
        return _industry(driver, str(snapshot.get("industry") or ""), fill_empty, ow)
    if section == "skills":
        return _skills(driver, list(snapshot.get("skills") or []), fill_empty, ow)
    if section == "photo":
        return _photo(driver, photo_path, bool(snapshot.get("has_photo")))
    if section == "experience":
        return _experience(driver, list(snapshot.get("experience") or []), fill_empty, ow)
    if section == "education":
        return _education(driver, list(snapshot.get("education") or []), fill_empty, ow)
    return "skipped"


def _headline(driver, text: str, fill_empty: bool, overwrite: bool) -> str:
    if not _should_write("", text, fill_empty=fill_empty, overwrite=overwrite):
        return "skipped"
    try:
        edit = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[aria-label*='headline' i], a[href*='edit/intro'], #top-card-text-edit-button")
            )
        )
        edit.click()
        inp = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[id*='headline'], input[name='headline'], textarea[id*='headline']")
            )
        )
        if not _should_write(_field_text(inp), text, fill_empty=fill_empty, overwrite=overwrite):
            driver.find_element(By.CSS_SELECTOR, "button[aria-label='Dismiss'], button[aria-label='Cancel']").click()
            return "skipped"
        _fill_input(inp, text)
        if not _save_modal(driver):
            return "failed"
        return "updated"
    except Exception as exc:
        logger.warning("LinkedIn headline sync failed: %s", exc)
        return "failed"


def _about(driver, text: str, fill_empty: bool, overwrite: bool) -> str:
    if not text.strip():
        return "skipped"
    try:
        edit = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "a[href*='edit/forms/summary/new'], button[aria-label*='About' i], #about-edit-button")
            )
        )
        edit.click()
        area = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[id*='summary'], textarea[name='summary']"))
        )
        if not _should_write(_field_text(area), text, fill_empty=fill_empty, overwrite=overwrite):
            _dismiss_modal(driver)
            return "skipped"
        _fill_textarea(area, text)
        if not _save_modal(driver):
            return "failed"
        return "updated"
    except Exception as exc:
        logger.warning("LinkedIn about sync failed: %s", exc)
        return "failed"


def _location(driver, text: str, fill_empty: bool, overwrite: bool) -> str:
    if not text.strip():
        return "skipped"
    try:
        edit = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='edit/forms/location/new'], button[aria-label*='location' i]"))
        )
        edit.click()
        inp = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[id*='location'], input[aria-label*='City' i]"))
        )
        if not _should_write(_field_text(inp), text, fill_empty=fill_empty, overwrite=overwrite):
            _dismiss_modal(driver)
            return "skipped"
        _fill_input(inp, text)
        inp.send_keys(Keys.ARROW_DOWN)
        time.sleep(0.3)
        inp.send_keys(Keys.ENTER)
        if not _save_modal(driver):
            return "failed"
        return "updated"
    except Exception as exc:
        logger.warning("LinkedIn location sync failed: %s", exc)
        return "failed"


def _industry(driver, text: str, fill_empty: bool, overwrite: bool) -> str:
    if not text.strip():
        return "skipped"
    try:
        edit = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='edit/forms/industry/new'], button[aria-label*='industry' i]"))
        )
        edit.click()
        inp = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[id*='industry'], input[aria-label*='Industry' i]"))
        )
        if not _should_write(_field_text(inp), text, fill_empty=fill_empty, overwrite=overwrite):
            _dismiss_modal(driver)
            return "skipped"
        _fill_input(inp, text)
        inp.send_keys(Keys.ARROW_DOWN)
        time.sleep(0.3)
        inp.send_keys(Keys.ENTER)
        if not _save_modal(driver):
            return "failed"
        return "updated"
    except Exception as exc:
        logger.warning("LinkedIn industry sync failed: %s", exc)
        return "failed"


def _skills(driver, skills: list, fill_empty: bool, overwrite: bool) -> str:
    if not skills:
        return "skipped"
    added = 0
    try:
        driver.get("https://www.linkedin.com/in/me/details/skills/")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "main")))
        for skill in skills[:15]:
            name = skill if isinstance(skill, str) else str(skill.get("name") or skill)
            name = name.strip()
            if not name:
                continue
            try:
                add_btn = driver.find_element(
                    By.CSS_SELECTOR,
                    "button[aria-label*='Add skill' i], a[href*='skill-add'], button[id*='skill-add']",
                )
                add_btn.click()
                inp = WebDriverWait(driver, 6).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='skill' i], input[aria-label*='Skill' i]"))
                )
                _fill_input(inp, name)
                inp.send_keys(Keys.ARROW_DOWN)
                time.sleep(0.2)
                inp.send_keys(Keys.ENTER)
                if _save_modal(driver, timeout=6):
                    added += 1
            except Exception:
                continue
        if added:
            return "updated"
        return "skipped" if fill_empty and not overwrite else "failed"
    except Exception as exc:
        logger.warning("LinkedIn skills sync failed: %s", exc)
        return "failed"


def _photo(driver, photo_path: str, has_photo: bool) -> str:
    path = (photo_path or "").strip()
    if not path or not has_photo or not Path(path).is_file():
        return "skipped"
    try:
        edit = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[aria-label*='photo' i], img.profile-photo-edit, button.profile-photo-edit__edit-button")
            )
        )
        edit.click()
        slot = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
        )
        slot.send_keys(str(Path(path).resolve()))
        time.sleep(1.5)
        if _save_modal(driver):
            return "updated"
        return "failed"
    except Exception as exc:
        logger.warning("LinkedIn photo sync failed: %s", exc)
        return "failed"


def _experience(driver, rows: list, fill_empty: bool, overwrite: bool) -> str:
    if not rows:
        return "skipped"
    if fill_empty and not overwrite:
        return "skipped"
    try:
        driver.get("https://www.linkedin.com/in/me/details/experience/")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "main")))
        row = rows[0] if isinstance(rows[0], dict) else {}
        title = str(row.get("title") or row.get("position") or "").strip()
        company = str(row.get("company") or row.get("organization") or "").strip()
        if not title and not company:
            return "skipped"
        add = driver.find_element(
            By.CSS_SELECTOR,
            "button[aria-label*='Add experience' i], a[href*='experience/add'], button[id*='experience-add']",
        )
        add.click()
        if title:
            t_inp = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[id*='title'], input[name='title']"))
            )
            _fill_input(t_inp, title)
        if company:
            c_inp = driver.find_element(By.CSS_SELECTOR, "input[id*='company'], input[name='companyName']")
            _fill_input(c_inp, company)
            time.sleep(0.5)
            c_inp.send_keys(Keys.ARROW_DOWN)
            c_inp.send_keys(Keys.ENTER)
        if _save_modal(driver):
            return "updated"
        return "failed"
    except Exception as exc:
        logger.warning("LinkedIn experience sync failed: %s", exc)
        return "skipped"


def _education(driver, rows: list, fill_empty: bool, overwrite: bool) -> str:
    if not rows:
        return "skipped"
    if fill_empty and not overwrite:
        return "skipped"
    try:
        driver.get("https://www.linkedin.com/in/me/details/education/")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "main")))
        row = rows[0] if isinstance(rows[0], dict) else {}
        school = str(row.get("school") or row.get("institution") or "").strip()
        degree = str(row.get("degree") or "").strip()
        if not school:
            return "skipped"
        add = driver.find_element(
            By.CSS_SELECTOR,
            "button[aria-label*='Add education' i], a[href*='education/add'], button[id*='education-add']",
        )
        add.click()
        s_inp = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[id*='school'], input[name='schoolName']"))
        )
        _fill_input(s_inp, school)
        time.sleep(0.5)
        s_inp.send_keys(Keys.ARROW_DOWN)
        s_inp.send_keys(Keys.ENTER)
        if degree:
            try:
                d_inp = driver.find_element(By.CSS_SELECTOR, "input[id*='degree'], input[name='degreeName']")
                _fill_input(d_inp, degree)
            except Exception:
                pass
        if _save_modal(driver):
            return "updated"
        return "failed"
    except Exception as exc:
        logger.warning("LinkedIn education sync failed: %s", exc)
        return "skipped"


def _dismiss_modal(driver) -> None:
    for css in ("button[aria-label='Dismiss']", "button[aria-label='Cancel']", "button.artdeco-modal__dismiss"):
        try:
            driver.find_element(By.CSS_SELECTOR, css).click()
            return
        except Exception:
            continue
