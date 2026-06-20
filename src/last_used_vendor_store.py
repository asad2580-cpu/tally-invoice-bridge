"""
last_used_vendor_store.py

Tracks which vendor was used most recently, so the vendor-picker screen
can default to it — speeds up batches of invoices from the same vendor,
without forcing the user to re-select every time.

Tiny, single-purpose store, deliberately separate from
vendor_template_store.py — this tracks a UI convenience preference,
not template data, and the two have very different lifetimes (this
value changes constantly during a session; templates change rarely).
"""

import json
import os

STORE_DIRECTORY = "local_data"
STORE_FILE_PATH = os.path.join(STORE_DIRECTORY, "last_used_vendor.json")


def _ensure_store_directory_exists() -> None:
    os.makedirs(STORE_DIRECTORY, exist_ok=True)


def set_last_used_vendor(vendor_key: str) -> bool:
    _ensure_store_directory_exists()
    temp_path = STORE_FILE_PATH + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump({"vendor_key": vendor_key}, f)
        os.replace(temp_path, STORE_FILE_PATH)
        return True
    except OSError:
        return False


def get_last_used_vendor() -> str | None:
    if not os.path.exists(STORE_FILE_PATH):
        return None
    try:
        with open(STORE_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("vendor_key")
    except (json.JSONDecodeError, OSError):
        return None