#!/usr/bin/env python3
"""Normalize production .env URL and cookie settings (run with sudo on EC2)."""
from pathlib import Path

ENV_PATH = Path("/home/ubuntu/applyxai/.env")
UPDATES = {
    "FRONTEND_URL": "https://applyxai.com",
    "CORS_ORIGINS": "https://applyxai.com,https://www.applyxai.com",
    "COOKIE_SECURE": "true",
}


def main() -> None:
    lines = ENV_PATH.read_text().splitlines()
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        if "=" not in line:
            out.append(line)
            continue
        key = line.split("=", 1)[0]
        if key in UPDATES:
            if key in seen:
                continue
            seen.add(key)
            out.append(f"{key}={UPDATES[key]}")
        else:
            out.append(line)
    for key, val in UPDATES.items():
        if key not in seen:
            out.append(f"{key}={val}")
    ENV_PATH.write_text("\n".join(out) + "\n")
    print("Updated", ENV_PATH)


if __name__ == "__main__":
    main()
