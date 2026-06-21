from datetime import datetime, timezone
from invoice_record_store import (
    InvoiceRecord, make_record_id, save_record, load_record,
    check_duplicate, list_all_records,
)

COMPANY = "Test1"
VENDOR = "Sharma Traders"
INVOICE_NO = "3"

record_id = make_record_id(COMPANY, VENDOR, INVOICE_NO)

print("=== Before any record exists ===")
print("Duplicate check (should be None):", check_duplicate(COMPANY, VENDOR, INVOICE_NO))

print("\n=== Saving a NOT-YET-PUSHED record ===")
record = InvoiceRecord(
    record_id=record_id,
    company_name=COMPANY,
    vendor_key=VENDOR,
    invoice_number=INVOICE_NO,
    voucher_date_yyyymmdd="20260601",
    party_ledger_name="Sharma Traders",
    narration="Invoice 3",
    lines=[
        {"ledger_name": "Purchase Account", "amount": 89898.00, "is_debit": True},
        {"ledger_name": "Sharma Traders", "amount": 89898.00, "is_debit": False},
    ],
    field_raw_text={"Date": "1-Jun-26", "Taxable Value": "89,898.00"},
    extracted_at_utc=datetime.now(timezone.utc).isoformat(),
)
save_record(record)
print("Duplicate check (should STILL be None - not pushed yet):", check_duplicate(COMPANY, VENDOR, INVOICE_NO))

print("\n=== Marking it as successfully pushed ===")
record.push_status = "pushed_success"
record.pushed_at_utc = datetime.now(timezone.utc).isoformat()
record.tally_response_summary = "Created: 1"
save_record(record)

print("Duplicate check (should now find it):")
dup = check_duplicate(COMPANY, VENDOR, INVOICE_NO)
print(f"  Found: {dup is not None}")
if dup:
    print(f"  Pushed at: {dup.pushed_at_utc}")

print("\n=== All records ===")
for r in list_all_records():
    print(f"  {r.record_id} -> {r.push_status}")