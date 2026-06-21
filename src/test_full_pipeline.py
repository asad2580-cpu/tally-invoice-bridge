"""
One-time manual test: runs the FULL pipeline end to end —
extract -> assemble -> push to Tally — with a confirmation prompt
before the actual push, same safety pattern as our earlier
tally_push_test.py.

This is NOT the real app flow (no review screen yet) — purely to prove
every module connects correctly before we build the proper UI around it.
"""

from invoice_text_extractor import extract_text_from_pdf
from voucher_assembler import assemble_purchase_voucher, AssemblyError
from tally_bridge import push_voucher

COMPANY_NAME = "Test1"
VENDOR_KEY = "Sharma Traders"
PDF_PATH = "sample_data/inv1.pdf"

result = extract_text_from_pdf(PDF_PATH)
if not result.success or not result.pages:
    print("Extraction failed:", result.error_message)
else:
    try:
        voucher = assemble_purchase_voucher(COMPANY_NAME, VENDOR_KEY, result.pages[0])
    except AssemblyError as e:
        print("Assembly failed:", e)
        raise SystemExit(1)

    print("=== VOUCHER ABOUT TO BE PUSHED ===")
    print("Company:", voucher.company_name)
    print("Type:", voucher.voucher_type)
    print("Date:", voucher.voucher_date_yyyymmdd)
    print("Party:", voucher.party_ledger_name)
    print("Narration:", voucher.narration)
    for line in voucher.lines:
        side = "DR" if line.is_debit else "CR"
        print(f"  {side}  {line.ledger_name:<25} {line.amount:>12,.2f}")
    print()

    confirm = input("Push this to Tally now? (y/n): ").strip().lower()
    if confirm == "y":
        push_result = push_voucher(
            company_name=voucher.company_name,
            voucher_type=voucher.voucher_type,
            voucher_date_yyyymmdd=voucher.voucher_date_yyyymmdd,
            party_ledger_name=voucher.party_ledger_name,
            lines=voucher.lines,
            narration=voucher.narration,
        )
        print("\nSuccess:", push_result.success)
        print("Created:", push_result.created_count)
        if not push_result.success:
            print("Error:", push_result.error_message)
    else:
        print("Cancelled — nothing was sent.")