#!/usr/bin/env python3
"""
Convert an IAM Secret Access Key to an Amazon SES SMTP password (SigV4).
Usage: python scripts/ses_smtp_password.py <SECRET_ACCESS_KEY> [region]
Default region: ap-southeast-2
"""
from __future__ import annotations

import hmac
import hashlib
import base64
import sys

VERSION = 0x04


def sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def smtp_password(secret_access_key: str, region: str) -> str:
    date = "11111111"
    service = "ses"
    terminal = "aws4_request"
    message = "SendRawEmail"
    version = bytes([VERSION])
    signature = sign(("AWS4" + secret_access_key).encode("utf-8"), date)
    signature = sign(signature, region)
    signature = sign(signature, service)
    signature = sign(signature, terminal)
    signature = sign(signature, message) + version
    return base64.b64encode(signature).decode("utf-8")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(1)
    secret = sys.argv[1].strip()
    region = (sys.argv[2] if len(sys.argv) > 2 else "ap-southeast-2").strip()
    print(smtp_password(secret, region))


if __name__ == "__main__":
    main()
