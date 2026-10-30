"""Detect LinkedIn / Naukri captcha and checkpoint pages so the worker can leave that source."""

from __future__ import annotations

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

_URL_HINTS = (
    "checkpoint",
    "authwall",
    "captcha",
    "challenge",
    "/check/add",
    "security-check",
    "securitycheck",
)

_TEXT_HINTS = (
    "verify you are a human",
    "verify you're a human",
    "are you a robot",
    "i'm not a robot",
    "i am not a robot",
    "security check",
    "unusual activity",
    "let's do a quick security check",
    "complete the security check",
    "solve this puzzle",
    "confirm you are human",
)

_FRAME_HINTS = ("recaptcha", "hcaptcha", "captcha", "arkoselabs", "funcaptcha")


def challenge_reason(driver: WebDriver, *, platform: str) -> str | None:
    """User-facing reason when the job site is asking for captcha or extra verification."""
    try:
        url = (driver.current_url or "").lower()
    except WebDriverException:
        return None
    if any(hint in url for hint in _URL_HINTS):
        return _message(platform)
    if _has_challenge_frame(driver) or _body_looks_like_challenge(driver):
        return _message(platform)
    return None


def _message(platform: str) -> str:
    name = (platform or "this site").strip() or "this site"
    return (
        f"{name} asked for a security check (captcha or extra verification). "
        "Complete it in Chrome, then continue."
    )


def _has_challenge_frame(driver: WebDriver) -> bool:
    try:
        frames = driver.find_elements(By.CSS_SELECTOR, "iframe[src], iframe[title]")
    except WebDriverException:
        return False
    for frame in frames:
        try:
            blob = f"{frame.get_attribute('src') or ''} {frame.get_attribute('title') or ''}".lower()
        except WebDriverException:
            continue
        if any(hint in blob for hint in _FRAME_HINTS):
            return True
    return False


def _body_looks_like_challenge(driver: WebDriver) -> bool:
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        text = (body.text or "")[:8000].lower()
    except WebDriverException:
        return False
    if "captcha" in text:
        return True
    return any(hint in text for hint in _TEXT_HINTS)
