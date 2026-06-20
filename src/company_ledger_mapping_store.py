"""
company_ledger_mapping_store.py

Stores and retrieves the COMPANY-LEVEL mapping from fixed invoice fields
(Taxable Value, CGST Amount, SGST Amount, IGST Amount, etc.) to the real
Tally ledger each one should post to.

This is set up once per company and reused across every vendor and every
invoice — unlike vendor_template_store.py, which tracks per-vendor box
POSITIONS on the page. This module tracks per-company ledger ASSIGNMENTS,
a different and much more stable piece of data.

Example: a company might always post "CGST Amount" to a ledger named
"Input CGST", regardless of which vendor the invoice came from. That
assignment lives here, set once, not re-asked for every vendor.

Storage: a single local JSON file, local_data/company_ledger_mappings.json.
Keyed by company_name, since a user may manage multiple Tally companies
through this tool over time.
"""

import json
import os
from datetime import datetime, timezone

STORE_DIRECTORY = "local_data"
STORE_FILE_PATH = os.path.join(STORE_DIRECTORY, "company_ledger_mappings.json")

# The fixed set of invoice fields that require a ledger mapping.
# This list is owned by us (the app), not fetched from Tally — these are
# the standard fields relevant to posting a purchase/sale journal entry.
# Extend this list as we support more field types later.
MAPPABLE_FIELDS = [
    "Taxable Value",
    "CGST Amount",
    "SGST Amount",
    "IGST Amount",
]


def _ensure_store_directory_exists() -> None:
    os.makedirs(STORE_DIRECTORY, exist_ok=True)


def _load_all_mappings() -> dict[str, dict]:
    """
    Loads the raw JSON store. Returns an empty dict if the file doesn't
    exist yet, or is unreadable/corrupted — a corrupted file should not
    crash the app, just be treated as "no mappings configured yet".
    """
    if not os.path.exists(STORE_FILE_PATH):
        return {}

    try:
        with open(STORE_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all_mappings(all_mappings: dict[str, dict]) -> bool:
    """
    Writes the full mapping store back to disk, atomically (write to a
    temp file, then rename into place) so an interrupted write can never
    leave a half-written, corrupted JSON file behind.
    """
    _ensure_store_directory_exists()
    temp_path = STORE_FILE_PATH + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(all_mappings, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, STORE_FILE_PATH)
        return True
    except OSError:
        return False


def save_company_mapping(company_name: str, field_to_ledger: dict[str, str]) -> bool:
    """
    Saves (or overwrites) the field-to-ledger mapping for a company.

    field_to_ledger should look like:
        {"Taxable Value": "Purchase Account", "CGST Amount": "Input CGST", ...}

    This does NOT validate that the ledger names actually exist in Tally —
    that check belongs to the caller (using tally_bridge.get_ledger_names),
    at the point where the user is picking ledgers in the UI, consistent
    with how we already validate before any voucher push.
    """
    all_mappings = _load_all_mappings()

    all_mappings[company_name] = {
        "company_name": company_name,
        "field_to_ledger": field_to_ledger,
        "last_updated_utc": datetime.now(timezone.utc).isoformat(),
    }

    return _save_all_mappings(all_mappings)


def load_company_mapping(company_name: str) -> dict[str, str] | None:
    """
    Returns the field-to-ledger dict for a company, or None if no
    mapping has been configured yet for this company (first-time setup
    needed).
    """
    all_mappings = _load_all_mappings()
    raw = all_mappings.get(company_name)
    if raw is None:
        return None
    return raw["field_to_ledger"]


def is_mapping_complete(company_name: str) -> bool:
    """
    Returns True only if every field in MAPPABLE_FIELDS has a ledger
    assigned. Useful for the UI to know whether to prompt the user to
    finish setup before letting them process invoices.
    """
    mapping = load_company_mapping(company_name)
    if mapping is None:
        return False
    return all(field in mapping and mapping[field] for field in MAPPABLE_FIELDS)


def list_companies_with_mappings() -> list[str]:
    """Returns all company names that have at least a partial mapping saved."""
    return list(_load_all_mappings().keys())