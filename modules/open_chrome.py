'''
Author:

Copyright (c) 2026 ApplyXAI

License:    MIT License
            https://opensource.org/license/mit
            
GitHub:     https://github.com/GodsScion/Auto_job_applier_linkedIn

Support me: https://github.com/sponsors/GodsScion

version:    26.01.20.5.08
'''

from modules.helpers import make_directories
from config.settings import run_in_background, auto_manage_driver, disable_extensions, safe_mode, file_name, failed_file_name, logs_folder_path, generated_resume_path
from config.questions import default_resume_path
if auto_manage_driver:
    import undetected_chromedriver as uc
else: 
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    # from selenium.webdriver.chrome.service import Service
import os, shutil, subprocess, sys, time
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from modules.helpers import (
    chrome_profile_extra_args,
    chrome_profile_launch_args,
    find_default_profile_directory,
    get_default_temp_profile,
    normalize_chrome_user_data_dir,
    critical_error_log,
    logger,
    print_lg,
)
from config._overrides import RUN_CONFIG_ENV
from modules import run_hooks
from modules.chrome_update import (
    looks_like_chrome_version_problem,
    prepare_chrome_for_run,
    read_chrome_major_version,
    refresh_chrome_and_retry_message,
)
from selenium.common.exceptions import SessionNotCreatedException

def _adhoc_sign(path: str) -> None:
    """Re-sign `path` ad-hoc on macOS. MUST run AFTER UC has patched the binary."""
    if sys.platform != "darwin":    return      # Gatekeeper is a macOS-only problem
    try:
        subprocess.run(["codesign", "--force", "--sign", "-", path], check=True, capture_output=True)
    except Exception as e:
        # Not fatal, plenty of Macs run unsigned binaries fine. Say what to look for if it isn't one.
        logger.warning("Couldn't ad-hoc re-sign the Chrome driver (%s). If Chrome dies with 'Status code was: -9', install the Xcode command line tools: xcode-select --install", type(e).__name__)


def platform_chromedriver_names() -> list[str]:
    """Preferred driver filenames for this OS (Windows x64 pin is chromedriver-win64.exe)."""
    if os.name == "nt":
        return ["chromedriver-win64.exe", "chromedriver.exe"]
    machine = ""
    try:
        machine = (os.uname().machine or "").lower()
    except AttributeError:
        machine = (os.environ.get("PROCESSOR_ARCHITECTURE") or "").lower()
    if sys.platform == "darwin":
        names = []
        if "arm" in machine or machine in {"aarch64", "arm64"}:
            names.append("chromedriver-mac-arm64")
        names.extend(["chromedriver-mac-x64", "chromedriver"])
        return names
    return ["chromedriver-linux64", "chromedriver"]


def bundled_chromedriver_path() -> str | None:
    """Prefer a pinned ChromeDriver shipped with Desktop / the worker, then env, then vendor/."""
    env = (os.environ.get("APPLYXAI_CHROMEDRIVER") or "").strip()
    names = platform_chromedriver_names()
    candidates = [env] if env else []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "") or ""
        exe_dir = os.path.dirname(sys.executable)
        dirs = [meipass, exe_dir, os.path.join(exe_dir, "chromedriver")]
        for folder in dirs:
            if not folder:
                continue
            for name in names:
                candidates.append(os.path.join(folder, name))
    else:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        vendor = os.path.join(root, "vendor")
        for name in names:
            candidates.append(os.path.join(vendor, name))
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def get_managed_driver_path() -> str | None:
    """Resolve a chromedriver that matches this machine's CPU, patch it, and re-sign it.

    Returns the path, or None to fall back to undetected_chromedriver's own download.

    Order: bundled/pinned driver, then Selenium Manager.

    ponytail: compatibility shim, not a driver manager. undetected-chromedriver 3.5.5
    (Feb 2024, the newest and final release, issue tracker returns HTTP 410) has no
    "mac-arm64" branch in Patcher._set_platform_name(), so every Apple Silicon user
    downloads an x86_64 driver and Chrome never launches:
        OSError: [Errno 86] Bad CPU type in executable
    Selenium Manager, already bundled with the installed selenium, resolves the right one.
    Ceiling: this fixes driver resolution and the Gatekeeper re-sign only, nothing else UC
    gets wrong. The real fix is upstream: UC is abandoned, the author's successor is
    `nodriver`. Delete this whole shim when the bot moves off UC.
    """
    try:
        bundled = bundled_chromedriver_path()
        if bundled:
            source = bundled
        else:
            from selenium.webdriver.common.selenium_manager import SeleniumManager
            source = SeleniumManager().binary_paths(["--browser", "chrome"])["driver_path"]
        # UC rewrites the driver in place, so never hand it the shared ~/.cache/selenium
        # copy that other tools use. Work on our own copy, in UC's own data dir.
        os.makedirs(uc.Patcher.data_path, exist_ok=True)
        ext = ".exe" if os.name == "nt" else ""
        # Per-process driver copy — parallel runs used to lock the same chromedriver.exe (WinError 32).
        target = os.path.join(uc.Patcher.data_path, f"chromedriver-{os.getpid()}{ext}")
        last_err: Exception | None = None
        for attempt in range(5):
            try:
                shutil.copy2(source, target)
                uc.Patcher(executable_path=target).auto()
                _adhoc_sign(target)
                return target
            except (PermissionError, OSError) as exc:
                last_err = exc
                time.sleep(0.5 * (attempt + 1))
        if last_err:
            raise last_err
    except Exception as e:
        logger.warning("Selenium Manager couldn't resolve a Chrome driver (%s: %s). Falling back to undetected_chromedriver's own download.", type(e).__name__, e)
        return None


def _launch_managed_chrome(options, driver_path: str | None, user_data_dir: str):
    major = read_chrome_major_version()
    kwargs = {"options": options, "user_data_dir": user_data_dir}
    if driver_path:
        kwargs["driver_executable_path"] = driver_path
    if major is not None:
        kwargs["version_main"] = major
    return uc.Chrome(**kwargs)


def _applyxai_supervised_run() -> bool:
    """True when ApplyXAI agent/worker launched this engine (never use personal Chrome)."""
    return bool(os.environ.get(RUN_CONFIG_ENV)) or bool(os.environ.get(run_hooks.PROFILE_ENV))


def _resolve_user_data_dir(*, is_retry: bool) -> tuple[str, str]:
    """Return (absolute user_data_dir, log label). Never uses personal Chrome unless explicitly allowed."""
    if is_retry:
        path = normalize_chrome_user_data_dir(get_default_temp_profile())
        return path, "guest retry profile"
    agent_profile_dir = run_hooks.profile_dir()
    if agent_profile_dir:
        path = normalize_chrome_user_data_dir(agent_profile_dir)
        return path, "ApplyXAI workspace profile"
    if _applyxai_supervised_run():
        path = normalize_chrome_user_data_dir(get_default_temp_profile())
        return path, "ApplyXAI isolated profile"
    profile_dir = find_default_profile_directory()
    if profile_dir and not safe_mode and os.environ.get("APPLYXAI_ALLOW_PERSONAL_CHROME") == "1":
        path = normalize_chrome_user_data_dir(profile_dir)
        return path, "personal Chrome (legacy)"
    path = normalize_chrome_user_data_dir(get_default_temp_profile())
    return path, "isolated automation profile"


def _apply_chrome_profile(options, user_data_dir: str) -> None:
    for flag in chrome_profile_extra_args():
        options.add_argument(flag)
    # undetected_chromedriver applies user_data_dir via constructor; duplicate flag confuses Chrome.
    if not auto_manage_driver:
        for flag in chrome_profile_launch_args(user_data_dir):
            options.add_argument(flag)


def createChromeSession(isRetry: bool = False, *, skip_update_check: bool = False):
    if not skip_update_check and not isRetry and not _applyxai_supervised_run():
        prepare_chrome_for_run()
    make_directories([file_name,failed_file_name,logs_folder_path+"/screenshots",default_resume_path,generated_resume_path+"/temp"])
    # Set up WebDriver with Chrome Profile
    options = uc.ChromeOptions() if auto_manage_driver else Options()
    # "--headless" is the legacy mode and is trivially detectable, "=new" runs the real browser.
    if run_in_background:   options.add_argument("--headless=new")
    if disable_extensions:  options.add_argument("--disable-extensions")

    print_lg("IF YOU HAVE MORE THAN 10 TABS OPENED, PLEASE CLOSE OR BOOKMARK THEM! Or it's highly likely that application will just open browser and not do anything!")
    user_data_dir, profile_label = _resolve_user_data_dir(is_retry=isRetry)
    print_lg(f"Chrome user-data-dir: {user_data_dir} ({profile_label})")
    _apply_chrome_profile(options, user_data_dir)
    if auto_manage_driver:
        print_lg("Setting up the matching Chrome driver... This may take some time (this happens each run when auto_manage_driver is enabled).")
        driver_path = get_managed_driver_path()
        last_err: Exception | None = None
        for attempt in range(4):
            try:
                driver = _launch_managed_chrome(options, driver_path, user_data_dir)
                break
            except Exception as exc:
                last_err = exc
                if looks_like_chrome_version_problem(exc) and attempt == 0:
                    refresh_chrome_and_retry_message()
                    driver_path = get_managed_driver_path()
                    continue
                if attempt >= 3:
                    raise
                print_lg(f"Chrome driver busy, retrying ({attempt + 1}/4)…")
                time.sleep(1.5 * (attempt + 1))
        else:
            if last_err:
                raise last_err
    else:
        # ponytail: warning only, no stealth patching here. Set auto_manage_driver = True if LinkedIn starts blocking.
        logger.warning("auto_manage_driver is False, so we're using plain Selenium with NO anti-detection at all. LinkedIn may flag or block this session, set auto_manage_driver = True in config/settings.py if that happens.")
        driver = webdriver.Chrome(options=options) #, service=Service(executable_path="C:\\Program Files\\Google\\Chrome\\chromedriver-win64\\chromedriver.exe"))
    driver.maximize_window()
    wait = WebDriverWait(driver, 45)
    actions = ActionChains(driver)
    return options, driver, actions, wait

options, driver, actions, wait = None, None, None, None
if os.environ.get("APPLYXAI_SKIP_CHROME_BOOTSTRAP") != "1":
    try:
        options, driver, actions, wait = createChromeSession()
    except SessionNotCreatedException as e:
        if looks_like_chrome_version_problem(e):
            refresh_chrome_and_retry_message()
            try:
                options, driver, actions, wait = createChromeSession(skip_update_check=True)
            except SessionNotCreatedException:
                logger.warning("Failed to create Chrome Session, retrying with guest profile", exc_info=True)
                options, driver, actions, wait = createChromeSession(True, skip_update_check=True)
        else:
            logger.warning("Failed to create Chrome Session, retrying with guest profile", exc_info=e)
            options, driver, actions, wait = createChromeSession(True, skip_update_check=True)
    except Exception as e:
        if looks_like_chrome_version_problem(e):
            refresh_chrome_and_retry_message()
            options, driver, actions, wait = createChromeSession(skip_update_check=True)
        else:
            msg = (
                "Chrome could not start (often another automation window is still open, or chromedriver is locked). "
                "Close extra Chrome/ApplyXAI windows and run .\\scripts\\kill_extra_workers.ps1, then try again."
            )
            if isinstance(e, TimeoutError):
                msg = "Couldn't download Chrome-driver. Set auto_manage_driver = False in config!"
            logger.error(msg)
            critical_error_log("In Opening Chrome", e)
            from pyautogui import alert

            alert(msg, "Error in opening chrome")
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
            raise SystemExit(1) from e

