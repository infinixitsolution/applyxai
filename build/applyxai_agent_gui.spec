# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for ApplyXAI Agent GUI Launcher

Builds a Windows executable with a tkinter GUI for the agent.
The GUI wraps the existing agent CLI commands.

Usage:
    pyinstaller build/applyxai_agent_gui.spec
"""

import os
import sys
from pathlib import Path


# Repository root
REPO_ROOT = Path(SPECPATH).parent
AGENT_ROOT = REPO_ROOT / "agent"
AUTOMATION_ROOT = REPO_ROOT / "automation"
MODULES_ROOT = REPO_ROOT / "modules"
CONFIG_ROOT = REPO_ROOT / "config"

# Hidden imports - packages PyInstaller might miss
HIDDEN_IMPORTS = [
    "agent",
    "agent.client",
    "agent.config",
    "agent.supervisor",
    "agent.gui",
    "agent.gui_theme",
    "agent.branding_paths",
    "agent.connect_flow",
    "agent.engine_bootstrap",
    "agent.win_process",
    "automation",
    "automation.events",
    "automation.run_config",
    "automation.runner",
    "automation.job_resume",
    "automation.qa_resolver",
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
    "selenium",
    "selenium.webdriver",
    "selenium.webdriver.common.by",
    "selenium.webdriver.support",
    "selenium.webdriver.chrome.options",
    "undetected_chromedriver",
    "requests",
    "langchain",
    "langchain_openai",
    "langchain_google_genai",
    "langgraph",
    "pyautogui",
    "flask",
]

# Data files to include
_BRANDING = REPO_ROOT / "agent" / "branding"
_ICON = _BRANDING / "applyxai.ico"

datas = [
    # Config schema
    (str(REPO_ROOT / "config_schema.py"), "."),
    # Main engine script
    (str(REPO_ROOT / "runAiBot.py"), "."),
    (str(_BRANDING / "mascot.png"), "agent/branding"),
    (str(_BRANDING / "applyxai.ico"), "agent/branding"),
]

# Collect all Python modules needed
def collect_package(package_root):
    """Recursively collect all .py files from a package directory."""
    root = Path(package_root)
    if not root.exists():
        return []
    sources = []
    for py_file in root.rglob("*.py"):
        rel_path = py_file.relative_to(root.parent)
        sources.append((str(py_file), str(rel_path.parent)))
    return sources

# Add agent package
datas.extend(collect_package(AGENT_ROOT))

# Add automation package
datas.extend(collect_package(AUTOMATION_ROOT))

# Add modules package
datas.extend(collect_package(MODULES_ROOT))

# Add config package
datas.extend(collect_package(CONFIG_ROOT))

# Tcl/Tk (required for tkinter in one-file builds; hook uses _tcl_data / _tk_data)
_tcl_root = Path(sys.base_prefix) / "tcl"
_tcl86 = _tcl_root / "tcl8.6"
_tk86 = _tcl_root / "tk8.6"
if not (_tcl86 / "init.tcl").is_file() or not _tk86.is_dir():
    raise SystemExit(f"ERROR: Tcl/Tk not found under {_tcl_root}. Install full Python with tkinter.")
datas.append((str(_tcl86), "_tcl_data"))
datas.append((str(_tk86), "_tk_data"))

# Main analysis
a = Analysis(
    [str(REPO_ROOT / "agent" / "gui.py")],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude backend/frontend not needed for agent
        "backend",
        "frontend",
        "pytest",
        "pytest.*",
        "sqlalchemy",  # backend only
        "psycopg2",  # backend only
        "redis",  # backend only
        "celery",  # backend only
        "fastapi",  # backend only
        "uvicorn",  # backend only
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Remove __pycache__ from collected files
a.datas = [x for x in a.datas if "__pycache__" not in x[0]]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ApplyXAI-Agent-GUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX can break Tcl init.tcl in one-file bundles
    console=False,  # Hide console for GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(_ICON) if _ICON.is_file() else None,
)
