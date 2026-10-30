# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the headless ApplyXAI Desktop agent worker."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

REPO_ROOT = Path(SPECPATH).parent
PRODUCT_VERSION = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip().splitlines()[0].strip()
AGENT_ROOT = REPO_ROOT / "agent"
AUTOMATION_ROOT = REPO_ROOT / "automation"
MODULES_ROOT = REPO_ROOT / "modules"
CONFIG_ROOT = REPO_ROOT / "config"

HIDDEN_IMPORTS = [
    "agent",
    "agent.client",
    "agent.config",
    "agent.supervisor",
    "agent.connect_flow",
    "agent.engine_bootstrap",
    "agent.win_process",
    "agent.local_wake",
    "agent.desktop_worker",
    "agent.credentials",
    "keyring",
    "keyring.backends",
    "keyring.backends.Windows",
    "keyring.backends.fail",
    "keyring.backends.null",
    "agent.live_capture_audio",
    "agent.live_capture_stdio",
    "soundcard",
    "numpy",
    "automation",
    "automation.events",
    "automation.run_config",
    "automation.runner",
    "automation.job_resume",
    "automation.qa_resolver",
    "automation.sources",
    "automation.sources.naukri",
    "automation.sources.naukri_links",
    "automation.sources.rotation",
    "automation.linkedin_profile",
    "automation.linkedin_profile.browser",
    "automation.linkedin_profile.sync",
    "automation.profile_sync_config",
    "automation.sources.history",
    "config",
    "config._overrides",
    "config.personals",
    "config.questions",
    "config.search",
    "config.secrets",
    "config.settings",
    "config.applyxai",
    "modules",
    "modules.run_hooks",
    "modules.open_chrome",
    "modules.helpers",
    "modules.clickers_and_finders",
    "modules.validator",
    "modules.updater",
    "modules.ai",
    "modules.ai.connections",
    "modules.ai.prompts",
    "selenium",
    "selenium.webdriver",
    "selenium.webdriver.common.by",
    "selenium.webdriver.support",
    "selenium.webdriver.chrome.options",
    "undetected_chromedriver",
    "requests",
    "langchain",
    "langchain.chat_models",
    "langchain_openai",
    "langchain_google_genai",
    "langgraph",
    "pyautogui",
    "flask",
]

for _pkg in ("langchain", "langchain_openai", "langchain_google_genai", "langgraph"):
    HIDDEN_IMPORTS.extend(collect_submodules(_pkg))
_sc_datas, _sc_bins, _sc_hidden = collect_all("soundcard")
HIDDEN_IMPORTS.extend(_sc_hidden)
HIDDEN_IMPORTS = sorted(set(HIDDEN_IMPORTS))

_BRANDING = REPO_ROOT / "agent" / "branding"
_ICON = _BRANDING / "applyxai.ico"

datas = [
    (str(REPO_ROOT / "VERSION"), "."),
    (str(REPO_ROOT / "config_schema.py"), "."),
    (str(REPO_ROOT / "runAiBot.py"), "."),
    (str(REPO_ROOT / "runLinkedInProfileSync.py"), "."),
    (str(_BRANDING / "mascot.png"), "agent/branding"),
    (str(_BRANDING / "applyxai.ico"), "agent/branding"),
]


def collect_package(package_root):
    root = Path(package_root)
    if not root.exists():
        return []
    sources = []
    for py_file in root.rglob("*.py"):
        rel_path = py_file.relative_to(root.parent)
        sources.append((str(py_file), str(rel_path.parent)))
    return sources


datas.extend(collect_package(AGENT_ROOT))
datas.extend(collect_package(AUTOMATION_ROOT))
datas.extend(collect_package(MODULES_ROOT))
datas.extend(collect_package(CONFIG_ROOT))
datas.extend(_sc_datas)

_CHROMEDRIVER_WIN64 = REPO_ROOT / "vendor" / "chromedriver-win64.exe"
_CHROMEDRIVER = REPO_ROOT / "vendor" / "chromedriver.exe"
if _CHROMEDRIVER_WIN64.is_file():
    _sc_bins = list(_sc_bins) + [(str(_CHROMEDRIVER_WIN64), ".")]
elif _CHROMEDRIVER.is_file():
    _sc_bins = list(_sc_bins) + [(str(_CHROMEDRIVER), ".")]

a = Analysis(
    [str(REPO_ROOT / "agent" / "desktop_worker.py")],
    pathex=[str(REPO_ROOT)],
    binaries=_sc_bins,
    datas=datas,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "backend",
        "frontend",
        "pytest",
        "pytest.*",
        "sqlalchemy",
        "psycopg2",
        "redis",
        "celery",
        "fastapi",
        "uvicorn",
        "tkinter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

a.datas = [x for x in a.datas if "__pycache__" not in x[0]]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=f"agent-worker-v{PRODUCT_VERSION}",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(_ICON) if _ICON.is_file() else None,
)
