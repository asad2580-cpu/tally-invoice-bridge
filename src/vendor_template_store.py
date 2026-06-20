"""
vendor_template_store.py

Stores and retrieves per-vendor field-box templates: the remembered
positions of fields (invoice number, date, party name, total amount, etc.)
on a given vendor's invoice layout, as drawn/corrected by the user.

Storage: a single local JSON file, local_data/vendor_templates.json.
Not synced anywhere, not uploaded — per the project's "local data stays
local" principle.

A template is identified by a vendor_key. Per earlier project decisions,
vendor_key should be the vendor's GSTIN when available, falling back to
a normalized vendor name when GSTIN isn't known. This module doesn't
decide that key itself — it just stores/retrieves whatever key it's
given. Key normalization/matching logic belongs in a separate module
(vendor identity matching — not yet built).
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

STORE_DIRECTORY = "local_data"
STORE_FILE_PATH = os.path.join(STORE_DIRECTORY, "vendor_templates.json")


@dataclass
class FieldBox:
    """A single field's remembered position on the invoice page."""
    x0: float
    x1: float
    top: float
    bottom: float


@dataclass
class VendorTemplate:
    vendor_key: str
    fields: dict[str, FieldBox]
    last_updated_utc: str  # ISO timestamp, set automatically on save


def _ensure_store_directory_exists() -> None:
    os.makedirs(STORE_DIRECTORY, exist_ok=True)


def _load_all_templates() -> dict[str, dict]:
    """
    Loads the raw JSON store as a plain dict. Returns an empty dict if
    the file doesn't exist yet (first run) or is unreadable/corrupted
    (we don't want a corrupted file to crash the whole app — we treat
    it as "no templates yet" and let the user rebuild from there).
    """
    if not os.path.exists(STORE_FILE_PATH):
        return {}

    try:
        with open(STORE_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all_templates(all_templates: dict[str, dict]) -> bool:
    """
    Writes the full template store back to disk. Returns True on success,
    False if the write failed for any reason (disk full, permissions, etc).

    Writes to a temporary file first, then renames it into place. This
    avoids leaving a half-written, corrupted JSON file if the process is
    interrupted mid-write (e.g. app crash, power loss) — the rename step
    is effectively atomic on both Windows and standard filesystems.
    """
    _ensure_store_directory_exists()
    temp_path = STORE_FILE_PATH + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(all_templates, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, STORE_FILE_PATH)
        return True
    except OSError:
        return False


def save_template(vendor_key: str, fields: dict[str, FieldBox]) -> bool:
    """
    Saves (or overwrites) the template for a given vendor. Overwriting is
    intentional: when a user corrects a field, we want the new position
    to fully replace the old one, not merge ambiguously.
    """
    all_templates = _load_all_templates()

    all_templates[vendor_key] = {
        "vendor_key": vendor_key,
        "fields": {name: asdict(box) for name, box in fields.items()},
        "last_updated_utc": datetime.now(timezone.utc).isoformat(),
    }

    return _save_all_templates(all_templates)


def load_template(vendor_key: str) -> VendorTemplate | None:
    """
    Returns the saved template for a vendor, or None if no template
    exists yet for this vendor_key (i.e. this is a first-time vendor
    and the user needs to draw boxes from scratch).
    """
    all_templates = _load_all_templates()
    raw = all_templates.get(vendor_key)
    if raw is None:
        return None

    fields = {
        name: FieldBox(**box_data)
        for name, box_data in raw["fields"].items()
    }
    return VendorTemplate(
        vendor_key=raw["vendor_key"],
        fields=fields,
        last_updated_utc=raw["last_updated_utc"],
    )


def list_known_vendors() -> list[str]:
    """Returns all vendor_keys that currently have a saved template."""
    return list(_load_all_templates().keys())


def delete_template(vendor_key: str) -> bool:
    """
    Removes a vendor's template entirely — useful if a user wants to
    force "start fresh" for a vendor whose layout changed significantly
    rather than nudging an existing template.
    """
    all_templates = _load_all_templates()
    if vendor_key not in all_templates:
        return False

    del all_templates[vendor_key]
    return _save_all_templates(all_templates)