"""
invoice_record_store.py

Persists a durable, reviewable record of every invoice processed:
what was extracted, what voucher was assembled, and whether/when it
was pushed to Tally — plus the duplicate-push guard, which checks
whether an invoice has already been successfully pushed before.

Storage: local_data/invoice_records.json, one entry per invoice,
keyed by a record_id (company + vendor + invoice number, normalized).
This is the audit trail described early in the project's design:
nothing should be pushed to Tally without a reviewable record existing
first.
"""

import json
import os
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

STORE_DIRECTORY = "local_data"
STORE_FILE_PATH = os.path.join(STORE_DIRECTORY, "invoice_records.json")


@dataclass
class InvoiceRecord:
    record_id: str
    company_name: str
    vendor_key: str
    invoice_number: str
    voucher_date_yyyymmdd: str
    party_ledger_name: str
    narration: str
    lines: list[dict]  # serialized LedgerLine data: {ledger_name, amount, is_debit}
    field_raw_text: dict[str, str]
    extracted_at_utc: str
    push_status: str = "not_pushed"  # "not_pushed", "pushed_success", "pushed_failed"
    pushed_at_utc: str | None = None
    tally_response_summary: str | None = None


def make_record_id(company_name: str, vendor_key: str, invoice_number: str) -> str:
    """
    Builds a stable, normalized ID for duplicate detection. Lowercased
    and stripped so trivial differences (case, surrounding whitespace
    from a slightly-off box) don't defeat the duplicate check.
    """
    parts = [company_name.strip().lower(), vendor_key.strip().lower(), invoice_number.strip().lower()]
    return "|".join(parts)


def _ensure_store_directory_exists() -> None:
    os.makedirs(STORE_DIRECTORY, exist_ok=True)


def _load_all_records() -> dict[str, dict]:
    if not os.path.exists(STORE_FILE_PATH):
        return {}
    try:
        with open(STORE_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all_records(all_records: dict[str, dict]) -> bool:
    _ensure_store_directory_exists()
    temp_path = STORE_FILE_PATH + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(all_records, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, STORE_FILE_PATH)
        return True
    except OSError:
        return False


def save_record(record: InvoiceRecord) -> bool:
    all_records = _load_all_records()
    all_records[record.record_id] = asdict(record)
    return _save_all_records(all_records)


def load_record(record_id: str) -> InvoiceRecord | None:
    all_records = _load_all_records()
    raw = all_records.get(record_id)
    return InvoiceRecord(**raw) if raw else None


def check_duplicate(company_name: str, vendor_key: str, invoice_number: str) -> InvoiceRecord | None:
    """
    Returns the existing record if this invoice has already been
    SUCCESSFULLY pushed before, or None if it's safe to proceed.

    A record that exists but failed to push, or was never pushed, does
    NOT count as a duplicate — the user should be able to retry those
    freely. Only a confirmed successful push is treated as "already done".
    """
    record_id = make_record_id(company_name, vendor_key, invoice_number)
    existing = load_record(record_id)
    if existing and existing.push_status == "pushed_success":
        return existing
    return None


def list_all_records() -> list[InvoiceRecord]:
    all_records = _load_all_records()
    return [InvoiceRecord(**raw) for raw in all_records.values()]