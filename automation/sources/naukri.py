"""Naukri on-site apply.

Naukri Apply is the Easy Apply equivalent. A click that leaves naukri.com is an
external application. Keyword and location come from the same search settings as LinkedIn.
"""

from __future__ import annotations

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from automation.sources.naukri_links import (
    classify_apply,
    is_submit_control,
    job_id_from_url,
    job_page_url,
    keep_leaf_chat_options,
    listing_skip_reason,
    search_url,
)

_LOGIN_URL = "https://www.naukri.com/nlogin/login"
_HOME_URL = "https://www.naukri.com/"
_CARD_CSS = "div.srp-jobtuple-wrapper, article.jobTuple, div.cust-job-tuple"
_NEXT_XPATH = (
    "//a[contains(@class,'next') or normalize-space()='Next' or @aria-label='Next']"
    " | //button[normalize-space()='Next' or @aria-label='Next']"
)


def is_logged_in(driver: WebDriver) -> bool:
    try:
        url = (driver.current_url or "").lower()
    except WebDriverException:
        return False
    if "nlogin" in url or "/login" in url:
        return False
    selectors = (
        "a[href*='/mnjuser/profile']",
        ".nI-gNb-drawer__bars",
        ".view-profile-wrapper",
        "#ni-gnb-header-section a.nI-gNb-header__nav-link",
    )
    for css in selectors:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, css):
                if el.is_displayed():
                    return True
        except WebDriverException:
            continue
    return False


def _type_first(driver: WebDriver, selectors: tuple[str, ...], value: str) -> bool:
    for css in selectors:
        try:
            fields = driver.find_elements(By.CSS_SELECTOR, css)
        except WebDriverException:
            continue
        for field in fields:
            try:
                if not field.is_displayed():
                    continue
                field.clear()
                field.send_keys(value)
                return True
            except WebDriverException:
                continue
    return False


def _submit_login(driver: WebDriver) -> None:
    for css in ("button[type='submit']", "button.blue-btn", "button.loginButton"):
        try:
            buttons = driver.find_elements(By.CSS_SELECTOR, css)
        except WebDriverException:
            continue
        for button in buttons:
            try:
                if button.is_displayed():
                    button.click()
                    return
            except WebDriverException:
                continue


def _saved_naukri_login() -> tuple[str, str]:
    try:
        from config.secrets import naukri_password, naukri_username
    except ImportError:
        return "", ""
    email = str(naukri_username or "").strip()
    password = str(naukri_password or "").strip()
    return email, password


def try_auto_login(driver: WebDriver) -> bool:
    """Fill the Naukri login form from credentials saved on this PC. False when none are saved."""
    email, password = _saved_naukri_login()
    if not email or not password:
        return False
    if not _type_first(driver, ("#usernameField", "input[type='text']", "input[name='email']"), email):
        return False
    if not _type_first(driver, ("#passwordField", "input[type='password']"), password):
        return False
    _submit_login(driver)
    return True


def ensure_login(driver: WebDriver) -> bool:
    import runAiBot as bot

    try:
        driver.get(_HOME_URL)
    except WebDriverException:
        return False
    if is_logged_in(driver):
        return True
    try:
        driver.get(_LOGIN_URL)
    except WebDriverException:
        return False
    if try_auto_login(driver):
        bot.buffer(3)
        if is_logged_in(driver):
            return True
    bot.run_hooks.emit("login_required", platform="naukri")
    bot.manual_login_retry(lambda: is_logged_in(driver), 2)
    return is_logged_in(driver)


def _text(el: WebElement) -> str:
    try:
        return " ".join((el.text or "").split())
    except WebDriverException:
        return ""


def _card_fields(card: WebElement) -> tuple[str, str, str, str, str]:
    job_id = (card.get_attribute("data-job-id") or "").strip()
    title_el = _first(card, "a.title, a.jobTupleHeader, a[href*='job-listings']")
    title = _text(title_el) if title_el else ""
    href = ""
    if title_el is not None:
        href = title_el.get_attribute("href") or ""
    if not job_id:
        job_id = job_id_from_url(href)
    company_el = _first(card, "a.comp-name, span.comp-name, a.subTitle")
    company = _text(company_el) if company_el else ""
    loc_el = _first(card, ".locWdth, .loc-wrap span, span.loc")
    location = _text(loc_el) if loc_el else ""
    return job_id, title, company, location, href


def _first(root: WebElement, css: str) -> WebElement | None:
    try:
        found = root.find_elements(By.CSS_SELECTOR, css)
    except WebDriverException:
        return None
    for el in found:
        try:
            if el.is_displayed():
                return el
        except WebDriverException:
            continue
    return found[0] if found else None


def _visible_controls(driver: WebDriver) -> list[WebElement]:
    found = []
    try:
        elements = driver.find_elements(By.XPATH, "//button|//a")
    except WebDriverException:
        return found
    for el in elements:
        try:
            if el.is_displayed() and _text(el):
                found.append(el)
        except WebDriverException:
            continue
    return found


def _pick_apply(driver: WebDriver) -> tuple[str, WebElement | None]:
    onsite = None
    external = None
    for el in _visible_controls(driver):
        label = _text(el)
        low = label.lower()
        if "filter" in low or "search" in low:
            continue
        kind = classify_apply(label, False)
        if kind == "external" and "apply" in low:
            external = el
        elif kind == "onsite" and (low == "apply" or low.startswith("apply")) and onsite is None:
            onsite = el
    if onsite is not None:
        return "onsite", onsite
    if external is not None:
        return "external", external
    return "", None


def _description(driver: WebDriver) -> str:
    for css in (".styles_JDC__dang-inner-html", "div.job-desc", "section.job-desc", ".dang-inner-html"):
        el = _first_driver(driver, css)
        if el is not None:
            text = _text(el)
            if len(text) > 40:
                return text[:20000]
    return ""


def _first_driver(driver: WebDriver, css: str) -> WebElement | None:
    try:
        found = driver.find_elements(By.CSS_SELECTOR, css)
    except WebDriverException:
        return None
    return found[0] if found else None


def _click_next(driver: WebDriver) -> bool:
    try:
        buttons = driver.find_elements(By.XPATH, _NEXT_XPATH)
    except WebDriverException:
        return False
    for button in buttons:
        try:
            if button.is_displayed():
                button.click()
                return True
        except WebDriverException:
            continue
    return False


def _fill_questions(driver: WebDriver, *, description: str, title: str, company: str) -> None:
    import runAiBot as bot

    try:
        fields = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='tel'], input[type='number'], textarea, select")
    except WebDriverException:
        return
    for field in fields:
        try:
            if not field.is_displayed():
                continue
            existing = (field.get_attribute("value") or "").strip()
            if existing:
                continue
            label = (
                field.get_attribute("aria-label")
                or field.get_attribute("placeholder")
                or field.get_attribute("name")
                or "Question"
            )
            kind = (field.get_attribute("type") or field.tag_name or "text").lower()
            qtype = "textarea" if field.tag_name.lower() == "textarea" else ("select" if field.tag_name.lower() == "select" else kind)
            answer = bot.answer_common_questions(label, None)
            if not answer:
                answer = bot._qa_extra_answer(
                    label, label.lower(), qtype,
                    job_description=description, job_title=title, job_company=company,
                )
            if not answer:
                bot.run_hooks.emit(
                    "form_question", label=label, question_type=qtype, options=[],
                    needs_answer=True, platform="naukri",
                )
                continue
            if field.tag_name.lower() == "select":
                from selenium.webdriver.support.ui import Select
                try:
                    Select(field).select_by_visible_text(answer)
                except Exception:
                    field.send_keys(answer)
            else:
                field.clear()
                field.send_keys(answer)
            bot.run_hooks.emit(
                "form_question", label=label, question_type=qtype, options=[],
                needs_answer=False, platform="naukri",
            )
        except WebDriverException:
            continue


def _upload_resume(driver: WebDriver, path: str) -> None:
    if not path:
        return
    try:
        slots = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
    except WebDriverException:
        return
    for slot in slots:
        try:
            slot.send_keys(path)
            return
        except WebDriverException:
            continue


_DRAWER_CSS = (
    "[id*='ChatbotContainer'], [id*='chatbotContainer'], .chatbot_Drawer, "
    "[class*='chatbot_Drawer'], [class*='ChatbotDrawer'], [class*='applyChatbot']"
)
_QUESTION_CSS = (
    ".chatbot_ListItem.botItem .msg, .chatbot_ListItem .botMsg .msg, "
    ".botItem .msg, .botMsg .msg, [class*='botMsg'] .msg, "
    ".chatbot_ListItem.botItem, [class*='BotMessage']"
)
_TEXT_CSS = (
    ".chatbot_SendMessageContainer .textArea[contenteditable='true'], "
    ".chatbot_InputContainer .textArea[contenteditable='true'], "
    "div.textArea[contenteditable='true']"
)
_SEND_CSS = ".sendMsg, [class*='sendMsg']"
_APPLIED_PHRASES = ("successfully applied", "application has been sent", "applied successfully")


def _displayed(elements: list[WebElement]) -> list[WebElement]:
    shown = []
    for el in elements:
        try:
            if el.is_displayed():
                shown.append(el)
        except WebDriverException:
            continue
    return shown


def _chat_open(driver: WebDriver) -> bool:
    try:
        return bool(_displayed(driver.find_elements(By.CSS_SELECTOR, _DRAWER_CSS)))
    except WebDriverException:
        return False


def _latest_question(driver: WebDriver) -> str:
    try:
        messages = _displayed(driver.find_elements(By.CSS_SELECTOR, _QUESTION_CSS))
    except WebDriverException:
        return ""
    texts = [_text(el) for el in messages]
    texts = [text for text in texts if text and len(text) < 400]
    if not texts:
        return ""
    markers = (
        "?", "select", "qualification", "education", "course", "experience",
        "resume", "applied", "institute", "specialization", "specialisation",
        "passing year", "percentage", "notice",
    )
    for text in reversed(texts):
        lower = text.lower()
        if any(marker in lower for marker in markers):
            return text
    return texts[-1]


_CHIP_CSS = (
    ".ssrc__label, .ssrc__chip, .singleselect-radiobutton-container label, "
    ".chatbot_Chip, [class*='chatbot_Chip'], [class*='quickReply'], "
    "[class*='QuickReply'], [class*='chip'], "
    "[role='radio'], [role='option'], button[class*='chip']"
)


def _drawers(driver: WebDriver) -> list[WebElement]:
    try:
        return _displayed(driver.find_elements(By.CSS_SELECTOR, _DRAWER_CSS))
    except WebDriverException:
        return []


def _chip_label(el: WebElement) -> str:
    label = _text(el)
    if label:
        return label
    for attr in ("aria-label", "title", "value"):
        try:
            value = " ".join((el.get_attribute(attr) or "").split())
        except WebDriverException:
            continue
        if value:
            return value
    return ""


def _chat_options(driver: WebDriver) -> list[tuple[WebElement, str]]:
    """Choices inside the apply chat only. The job page Apply button is not a choice."""
    options: list[tuple[WebElement, str]] = []
    seen: set[str] = set()
    roots = _drawers(driver)
    if not roots:
        return options
    for root in roots:
        try:
            elements = root.find_elements(By.CSS_SELECTOR, _CHIP_CSS)
        except WebDriverException:
            continue
        for el in _displayed(elements):
            label = _chip_label(el)
            key = label.lower()
            if not label or len(label) > 80 or "?" in label or key in seen:
                continue
            if key in {"send", "apply", "save"}:
                continue
            seen.add(key)
            options.append((el, label))
    kept = set(keep_leaf_chat_options([label for _el, label in options]))
    return [(el, label) for el, label in options if label in kept]


def _chat_text_box(driver: WebDriver) -> WebElement | None:
    try:
        boxes = _displayed(driver.find_elements(By.CSS_SELECTOR, _TEXT_CSS))
    except WebDriverException:
        return None
    return boxes[-1] if boxes else None


def _click_send(driver: WebDriver) -> bool:
    try:
        buttons = _displayed(driver.find_elements(By.CSS_SELECTOR, _SEND_CSS))
    except WebDriverException:
        return False
    for button in buttons:
        try:
            driver.execute_script("arguments[0].click();", button)
            return True
        except WebDriverException:
            continue
    return False


def _application_sent(driver: WebDriver) -> bool:
    question = _latest_question(driver).lower()
    if any(phrase in question for phrase in _APPLIED_PHRASES):
        return True
    try:
        body = (driver.find_element(By.TAG_NAME, "body").text or "")[:20000].lower()
    except WebDriverException:
        return False
    return any(phrase in body for phrase in _APPLIED_PHRASES)


def _same_question(left: str, right: str) -> bool:
    from automation.sources.naukri_links import actionable_question

    return actionable_question(left).lower() == actionable_question(right).lower()


def _profile_education() -> list:
    try:
        from config import applyxai as ax
    except ImportError:
        return []
    rows = getattr(ax, "education", None)
    return list(rows) if isinstance(rows, list) else []


def _chat_answer(question: str, options: list[str], *, description: str, title: str, company: str) -> str | None:
    import runAiBot as bot
    from automation.sources.naukri_links import (
        actionable_question, pick_education_option, pick_option, preferred_chat_answer,
    )

    asked = actionable_question(question)
    education = _profile_education()
    preset = preferred_chat_answer(
        asked, getattr(bot, "years_of_experience", None), education=education,
    )
    if options:
        matched = pick_option(preset, options) if preset else None
        if not matched:
            matched = pick_education_option(options, education)
        if matched:
            return matched
    elif preset:
        return preset
    label = asked.lower()
    answer = bot.answer_common_questions(label, None)
    if not answer:
        answer = bot._qa_extra_answer(
            asked or "qualification", label or "qualification", "radio" if options else "text",
            options=options or None,
            job_description=description, job_title=title, job_company=company,
        )
    if options:
        return pick_option(answer, options) or pick_education_option(options, education)
    return (answer or "").strip() or None


def _click_chat_choice(driver: WebDriver, target: WebElement) -> bool:
    try:
        driver.execute_script(
            "var el = arguments[0];"
            "el.click();"
            "if (el.parentElement) el.parentElement.click();",
            target,
        )
        return True
    except WebDriverException:
        try:
            target.click()
            return True
        except WebDriverException:
            return False


def _wait_for_next_question(driver: WebDriver, previous: str) -> str:
    """Return the next bot message, '__sent__' when the application is in, or '' if it did not move."""
    import runAiBot as bot

    for _ in range(14):
        if _application_sent(driver):
            return "__sent__"
        if not _chat_open(driver):
            return "__closed__"
        current = _latest_question(driver)
        if current and not _same_question(current, previous):
            return current
        bot.buffer(1)
    return ""


def _upload_resume_in_chat(driver: WebDriver, path: str) -> bool:
    if not path:
        return False
    for root in _drawers(driver):
        try:
            slots = root.find_elements(By.CSS_SELECTOR, "input[type='file']")
        except WebDriverException:
            continue
        for slot in slots:
            try:
                slot.send_keys(path)
                return True
            except WebDriverException:
                continue
    return False


def _record_chat_answer(question: str, labels: list[str], *, typed: bool) -> None:
    import runAiBot as bot

    bot.run_hooks.emit(
        "form_question", label=question, question_type="text" if typed else "radio",
        options=labels, needs_answer=False, platform="naukri",
    )


def _missing_chat_answer(question: str, labels: list[str]) -> tuple[bool, str]:
    import runAiBot as bot

    bot.run_hooks.emit(
        "form_question", label=question or "Naukri application question",
        question_type="radio" if labels else "text", options=labels,
        needs_answer=True, platform="naukri",
    )
    return False, f"Naukri asked a question that has no saved answer: {question or 'application question'}"


def _walk_apply_chat(
    driver: WebDriver, *, description: str, title: str, company: str, resume_path: str,
) -> tuple[bool, str]:
    """Answer Naukri's apply chat one question at a time.

    A resume is attached only when the chat asks for one. Choice questions are clicked.
    They are never typed into the message box, because that makes Naukri repeat the question.

    (True, "") means the application was sent. (False, "") means no chat opened.
    """
    import runAiBot as bot
    from automation.sources.naukri_links import actionable_question, chat_step

    for _ in range(10):
        if _chat_open(driver):
            break
        bot.buffer(1)
    else:
        return False, ""

    for _step in range(24):
        if _application_sent(driver):
            return True, ""
        question = _latest_question(driver)
        options = _chat_options(driver)
        if not question and not options:
            bot.buffer(1)
            continue
        asked = actionable_question(question)
        step = chat_step(asked)
        if not options and step == "choice":
            for _wait in range(8):
                bot.buffer(1)
                options = _chat_options(driver)
                if options:
                    break
        labels = [label for _el, label in options]
        if options:
            answer = _chat_answer(
                asked, labels, description=description, title=title, company=company,
            )
            target = next((el for el, label in options if label == answer), None)
            if target is None and answer:
                target = next(
                    (el for el, label in options if label.lower() == answer.lower()),
                    None,
                )
            if target is None:
                return _missing_chat_answer(asked, labels)
            if not _click_chat_choice(driver, target):
                return False, f"Naukri is still asking: {question}"
            _record_chat_answer(asked, labels, typed=False)
        elif step == "resume":
            if not _upload_resume_in_chat(driver, resume_path):
                return False, "Naukri asked for a resume and the file could not be attached."
            _record_chat_answer(asked, [], typed=False)
        else:
            text_box = _chat_text_box(driver)
            if text_box is None:
                bot.buffer(1)
                continue
            answer = _chat_answer(
                asked, [], description=description, title=title, company=company,
            )
            if not answer:
                return _missing_chat_answer(asked, [])
            try:
                text_box.click()
                text_box.send_keys(answer)
            except WebDriverException:
                return False, f"Naukri is still asking: {question}"
            if not _click_send(driver):
                try:
                    from selenium.webdriver.common.keys import Keys
                    text_box.send_keys(Keys.ENTER)
                except WebDriverException:
                    return False, f"Naukri is still asking: {question}"
            _record_chat_answer(asked, [], typed=True)
        nxt = _wait_for_next_question(driver, question)
        if nxt == "__sent__":
            return True, ""
        if nxt == "__closed__":
            if _application_sent(driver):
                return True, ""
            return False, "The Naukri apply chat closed before the application was sent."
        if not nxt:
            return False, f"Naukri is still asking: {question}"
    if _application_sent(driver):
        return True, ""
    return False, "The Naukri questions did not finish."


def _submit_drawer(driver: WebDriver, *, dry_run: bool) -> bool:
    """Click a real Submit/Send control. Never the job-page Apply button."""
    if dry_run:
        return False
    for el in _visible_controls(driver):
        if not is_submit_control(_text(el)):
            continue
        try:
            el.click()
            return True
        except WebDriverException:
            continue
    return False


def _apply_one(driver: WebDriver, card: WebElement, seen: set[str], applied_ids: set[str], cursor: dict) -> str:
    """Handle one result card. Returns submitted, external, skipped, failed, or ignore."""
    import runAiBot as bot

    job_id, title, company, work_location, href = _card_fields(card)
    if not job_id or job_id in seen or job_id in applied_ids:
        return "ignore"
    seen.add(job_id)
    cursor["seen"] = list(seen)
    job_link = href if href.startswith("https://") else job_page_url(job_id)
    list_handle = driver.current_window_handle
    list_url = driver.current_url
    try:
        driver.get(job_link)
    except WebDriverException:
        return "ignore"
    bot.buffer(1)
    description = _description(driver)
    bot.run_hooks.emit(
        "job_started", job_id=job_id, title=title or "Naukri job", company=company,
        work_location=work_location, work_style="", job_link=job_link, platform="naukri",
    )
    skip_reason = listing_skip_reason(
        title, company, description,
        bad_words=list(getattr(bot, "bad_words", None) or []),
        company_bad_words=list(getattr(bot, "about_company_bad_words", None) or []),
    )
    if skip_reason:
        bot.failed_job(
            job_id, job_link, "Pending", "Unknown", skip_reason, skip_reason,
            "Skipped", "Not Available", description=description,
        )
        bot.skip_count += 1
        return "skipped"
    kind, button = _pick_apply(driver)
    outcome = "skipped"
    try:
        if button is None:
            bot.failed_job(
                job_id, job_link, "Pending", "Unknown", "No Naukri Apply button",
                "This posting has no on-site Apply button.", "Skipped", "Not Available",
                description=description,
            )
            bot.skip_count += 1
            return "skipped"
        if kind == "external":
            _record_external(job_id, title, company, work_location, description, job_link, job_link)
            return "external"
        origin = driver.current_window_handle
        tabs_before = len(driver.window_handles)
        button.click()
        bot.buffer(1)
        if len(driver.window_handles) > tabs_before:
            external_link = job_link
            try:
                driver.switch_to.window(driver.window_handles[-1])
                external_link = driver.current_url or job_link
                if driver.current_window_handle != origin:
                    driver.close()
                driver.switch_to.window(origin)
            except WebDriverException:
                pass
            _record_external(job_id, title, company, work_location, description, job_link, external_link)
            return "external"
        resume_path, _resume_id = bot.prepare_job_resume(job_id, title, company, description)
        if bot.useNewResume and not resume_path:
            bot.run_hooks.emit(
                "skipped", job_id=job_id, job_link=job_link, platform="naukri",
                reason="Resume was not ready",
            )
            bot.skip_count += 1
            return "skipped"
        if bot.stop_before_submit:
            bot.run_hooks.emit(
                "skipped", job_id=job_id, job_link=job_link, platform="naukri",
                reason="Dry run: stopped before submit",
            )
            bot.skip_count += 1
            return "skipped"
        sent, chat_reason = _walk_apply_chat(
            driver, description=description, title=title, company=company, resume_path=resume_path,
        )
        if sent:
            bot.submitted_jobs(
                job_id, title, company, work_location, "", description, "Unknown",
                "Needs an AI", "Unknown", "Unknown", resume_path or "Pending", False,
                "Unknown", "Pending", job_link, "Easy Applied", None, "In Development",
            )
            bot.easy_applied_count += 1
            applied_ids.add(job_id)
            return "submitted"
        if chat_reason:
            _capture_failure_screenshot(driver, job_id, "Apply chat")
            bot.failed_job(
                job_id, job_link, "Pending", "Unknown",
                chat_reason, chat_reason, "Failed", "Not Available", description=description,
            )
            bot.failed_count += 1
            return "failed"
        _upload_resume(driver, resume_path)
        _fill_questions(driver, description=description, title=title, company=company)
        if not _submit_drawer(driver, dry_run=False):
            _capture_failure_screenshot(driver, job_id, "Submit")
            bot.failed_job(
                job_id, job_link, "Pending", "Unknown", "Naukri Apply was not submitted",
                "The submit control was not found.", "Failed", "Not Available",
                description=description,
            )
            bot.failed_count += 1
            return "failed"
        bot.buffer(2)
        if not _application_sent(driver):
            _capture_failure_screenshot(driver, job_id, "Submit unconfirmed")
            bot.failed_job(
                job_id, job_link, "Pending", "Unknown", "Naukri Apply was not confirmed as sent",
                "Submit was clicked but Naukri did not show a success message.", "Failed",
                "Not Available", description=description,
            )
            bot.failed_count += 1
            return "failed"
        bot.submitted_jobs(
            job_id, title, company, work_location, "", description, "Unknown",
            "Needs an AI", "Unknown", "Unknown", resume_path or "Pending", False,
            "Unknown", "Pending", job_link, "Easy Applied", None, "In Development",
        )
        bot.easy_applied_count += 1
        applied_ids.add(job_id)
        outcome = "submitted"
        return outcome
    except WebDriverException as exc:
        bot.failed_job(
            job_id, job_link, "Pending", "Unknown", "Naukri Apply could not be opened",
            exc, "Skipped", "Not Available", description=description,
        )
        bot.skip_count += 1
        return "skipped"
    finally:
        try:
            if driver.current_window_handle != list_handle:
                driver.switch_to.window(list_handle)
            if driver.current_url != list_url:
                driver.get(list_url)
                bot.buffer(1)
        except WebDriverException:
            pass


def _record_external(job_id, title, company, work_location, description, job_link, application_link) -> None:
    import runAiBot as bot

    bot.external_jobs_count += 1
    bot.submitted_jobs(
        job_id, title, company, work_location, "", description, "Unknown",
        "Needs an AI", "Unknown", "Unknown", "Pending", False, "Unknown", "Pending",
        job_link, application_link or job_link, None, "In Development",
    )


def _capture_failure_screenshot(driver: WebDriver, job_id: str, stage: str) -> None:
    import runAiBot as bot

    try:
        bot.screenshot(driver, job_id, f"Naukri {stage}")
    except Exception:
        pass


def _challenge_block(driver: WebDriver, submitted: int) -> tuple[str, int, str] | None:
    from automation.sources.challenges import challenge_reason

    reason = challenge_reason(driver, platform="Naukri")
    if not reason:
        return None
    import runAiBot as bot
    bot.run_hooks.emit("login_required", platform="naukri")
    return "blocked", submitted, reason


def apply_batch(
    driver: WebDriver,
    search_terms: list[str],
    location: str,
    *,
    max_successful: int | None,
    cursor: dict,
) -> tuple[str, int, str]:
    """Apply on Naukri until the switch budget, the search is finished, or login blocks the run.

    Returns (status, submitted_count, reason). status is limit, exhausted, or blocked.
    """
    import runAiBot as bot

    if not ensure_login(driver):
        blocked = _challenge_block(driver, 0)
        if blocked:
            return blocked
        return "blocked", 0, "Sign in to Naukri to continue."
    blocked = _challenge_block(driver, 0)
    if blocked:
        return blocked

    terms = list(cursor.get("terms") or search_terms)
    cursor["terms"] = terms
    term_index = int(cursor.get("term_index") or 0)
    seen = {str(item) for item in (cursor.get("seen") or [])}
    applied_ids = bot.get_applied_job_ids()
    submitted = 0

    for index, term in enumerate(terms):
        if index < term_index:
            continue
        cursor["term_index"] = index
        years = getattr(bot, "years_of_experience", None)
        if years in (None, ""):
            years = getattr(bot, "current_experience", None)
        try:
            driver.get(search_url(
                term, location,
                date_posted=str(getattr(bot, "date_posted", "") or ""),
                experience_years=years,
            ))
        except WebDriverException:
            return "blocked", submitted, "The Naukri search page could not be opened."
        blocked = _challenge_block(driver, submitted)
        if blocked:
            return blocked
        bot.buffer(2)
        for _page in range(20):
            bot.run_hooks.checkpoint()
            blocked = _challenge_block(driver, submitted)
            if blocked:
                return blocked
            try:
                cards = driver.find_elements(By.CSS_SELECTOR, _CARD_CSS)
            except WebDriverException:
                return "blocked", submitted, "The Naukri results could not be read."
            if not cards:
                break
            for card_index in range(len(cards)):
                bot.run_hooks.checkpoint()
                blocked = _challenge_block(driver, submitted)
                if blocked:
                    return blocked
                try:
                    fresh = driver.find_elements(By.CSS_SELECTOR, _CARD_CSS)
                    card = fresh[card_index]
                except (WebDriverException, IndexError):
                    continue
                outcome = _apply_one(driver, card, seen, applied_ids, cursor)
                if outcome == "submitted":
                    submitted += 1
                    if max_successful is not None and submitted >= max_successful:
                        return "limit", submitted, ""
            if not _click_next(driver):
                break
            bot.buffer(2)
        cursor["term_index"] = index + 1
        cursor["page"] = 1

    cursor["term_index"] = len(terms)
    return "exhausted", submitted, ""
