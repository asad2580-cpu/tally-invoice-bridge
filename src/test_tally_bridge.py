"""
Quick manual test for tally_bridge.py — not a formal automated test yet,
just a way to confirm the consolidated module behaves like our earlier
standalone scripts did.
"""

from tally_bridge import get_ledger_names, push_voucher, LedgerLine

COMPANY_NAME = "Test1"

print("=== Testing get_ledger_names ===")
result = get_ledger_names(COMPANY_NAME)
print("Success:", result.success)
print("Ledgers:", result.ledger_names)
print("Error (if any):", result.error_message)

print("\n=== Testing push_voucher with a VALID ledger ===")
result = push_voucher(
    company_name=COMPANY_NAME,
    voucher_type="Purchase",
    voucher_date_yyyymmdd="20260601",
    party_ledger_name="Sharma Traders",
    lines=[
        LedgerLine(ledger_name="Purchase Account", amount=1234.50, is_debit=True),
        LedgerLine(ledger_name="Sharma Traders", amount=1234.50, is_debit=False),
    ],
    narration="Test via consolidated tally_bridge module",
)
print("Success:", result.success)
print("Created:", result.created_count)
print("Error (if any):", result.error_message)

print("\n=== Testing push_voucher with a MISSING ledger (should be blocked) ===")
result = push_voucher(
    company_name=COMPANY_NAME,
    voucher_type="Purchase",
    voucher_date_yyyymmdd="20260601",
    party_ledger_name="Totally Fake Ledger XYZ",
    lines=[
        LedgerLine(ledger_name="Purchase Account", amount=999.00, is_debit=True),
        LedgerLine(ledger_name="Totally Fake Ledger XYZ", amount=999.00, is_debit=False),
    ],
    narration="This should never reach Tally",
)
print("Success:", result.success)
print("Error (if any):", result.error_message)