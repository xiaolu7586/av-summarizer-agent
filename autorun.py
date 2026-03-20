#!/usr/bin/env python3
"""
autorun.py — Write formData config to .secrets/transcribe-config.json
Runs once on first activation if formData is provided by the platform.
"""
import json
import os
import sys
import tempfile

SECRETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".secrets")
TARGET = os.path.join(SECRETS_DIR, "transcribe-config.json")


def main():
    raw = sys.stdin.read().strip() if not sys.stdin.isatty() else "{}"
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {}

    # Only write if at least one value is provided
    if not any(data.get(k, "").strip() for k in ("transcribe_api_key", "transcribe_base_url")):
        return

    os.makedirs(SECRETS_DIR, exist_ok=True)

    tmp_fd, tmp_path = tempfile.mkstemp(dir=SECRETS_DIR, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, TARGET)
        print(f"Config saved to {TARGET}")
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


if __name__ == "__main__":
    main()
