#!/usr/bin/env python3
"""
autorun.py — Write formData config to .secrets/transcribe-config.json
Runs automatically on first activation if the user has provided config fields.
"""

import json
import os
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.resolve()
SECRETS_DIR = WORKSPACE_ROOT / ".secrets"
CONFIG_PATH = SECRETS_DIR / "transcribe-config.json"


def main():
    raw = os.environ.get("OPENCLAW_FORM_DATA") or (sys.stdin.read().strip() if not sys.stdin.isatty() else "")
    if not raw:
        return

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return

    api_key = data.get("transcribe_api_key", "").strip()
    base_url = data.get("transcribe_base_url", "").strip()

    if not api_key and not base_url:
        return

    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    config = {}
    if CONFIG_PATH.exists():
        try:
            config = json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass

    if api_key:
        config["transcribe_api_key"] = api_key
    if base_url:
        config["transcribe_base_url"] = base_url

    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, ensure_ascii=False, indent=2))
    tmp.replace(CONFIG_PATH)
    print(f"Transcription config saved to {CONFIG_PATH}")


if __name__ == "__main__":
    main()
