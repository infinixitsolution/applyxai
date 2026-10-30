# Documentation

Everything about the LinkedIn AI Auto Job Applier that does not fit on the
[front page](../README.md).

## Getting started

| Page | What is in it |
|---|---|
| [Installation](install.md) | Python, Chrome, the packages, the Chrome driver, and how to run the bot and the control panel |
| [Configuration](configuration.md) | How configuration works, the order to do it in, and the rules that apply to every config file |

## Configuration reference

One page per file in `config/`.

| Page | Covers |
|---|---|
| [`config/personals.py`](config-personals.md) | Name, phone, address, equal-opportunity answers |
| [`config/questions.py`](config-questions.md) | Easy Apply answers: experience, work authorization, salary, notice period, resume, pause behaviour |
| [`config/search.py`](config-search.md) | Search terms, LinkedIn filters, skip rules, visa-sponsorship filtering |
| [`config/secrets.py`](config-secrets.md) | LinkedIn login and the optional AI setup |
| [`config/settings.py`](config-settings.md) | How the bot runs: click gap, background mode, safe mode, dry runs, logs |

## SaaS audit (ApplyXAI product)

| Page | What is in it |
|---|---|
| **[AUDIT.md](AUDIT.md)** | **Master end-to-end audit report** (2026-10-16): architecture, tests, security, readiness |
| **[PENDING_PARTIAL_WORK.md](PENDING_PARTIAL_WORK.md)** | **Single-page inventory** of open and partial work (2026-10-17) |
| [BACKLOG.md](BACKLOG.md) | Canonical backlog #1–#70 |
| [P0_LAUNCH_CHECKLIST.md](P0_LAUNCH_CHECKLIST.md) | Production launch blockers only |
| [AUDIT_FINDINGS.md](AUDIT_FINDINGS.md) | Prioritized finding register |
| [TESTING_REPORT.md](TESTING_REPORT.md) | Baseline pytest results |
| [WINDOWS_SETUP.md](WINDOWS_SETUP.md) | Verified Windows dev startup (API **8010**, frontend **5173**) |
| [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) | Launch blockers and beta criteria |

## Project

| Page | What is in it |
|---|---|
| [Contributing](../CONTRIBUTING.md) | Code guidelines, where to send pull requests, running the tests, licensing of contributions |
| [Contributors and the MIT relicense record](contributor-consent/contributors.md) | Acknowledgements for the AGPL-era contributors, and how the relicense was done |
| [Disclaimer, Terms and License](legal.md) | Read this before you use the tool |
| [Support and community](support.md) | Discord, GitHub Discussions, socials, sponsoring |
| [Releases](https://github.com/GodsScion/Auto_job_applier_linkedIn/releases) | Version history and release notes |

---

[← Back to the project README](../README.md)
