from invoice_text_extractor import extract_text_from_pdf
from voucher_assembler import assemble_purchase_voucher, AssemblyError

COMPANY_NAME = "Test1"
VENDOR_KEY = "Sharma Traders"
PDF_PATH = "sample_data/inv1.pdf"

result = extract_text_from_pdf(PDF_PATH)
if not result.success or not result.pages:
    print("Extraction failed:", result.error_message)
else:
    try:
        voucher = assemble_purchase_voucher(COMPANY_NAME, VENDOR_KEY, result.pages[0])

        print("=== ASSEMBLED VOUCHER ===")
        print("Company:", voucher.company_name)
        print("Type:", voucher.voucher_type)
        print("Date:", voucher.voucher_date_yyyymmdd)
        print("Party ledger:", voucher.party_ledger_name)
        print("Narration:", voucher.narration)
        print("\nLines:")
        for line in voucher.lines:
            side = "DR" if line.is_debit else "CR"
            print(f"  {side}  {line.ledger_name:<25} {line.amount:>12,.2f}")

        total_dr = sum(l.amount for l in voucher.lines if l.is_debit)
        total_cr = sum(l.amount for l in voucher.lines if not l.is_debit)
        print(f"\nTotal Dr: {total_dr:,.2f}   Total Cr: {total_cr:,.2f}")
        print("Balanced:", total_dr == total_cr)

        print("\nRaw box text per field:")
        for field, text in voucher.field_raw_text.items():
            print(f"  {field}: '{text}'")

    except AssemblyError as e:
        print("Assembly failed:", e)