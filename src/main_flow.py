"""
main_flow.py

The real entry point for processing one invoice: pick a vendor, then
label (or auto-load) that vendor's field boxes on the invoice page.

This replaces running vendor_picker_ui.py and box_labeling_ui.py as
separate standalone scripts — they're now stages in one flow.
"""
from vendor_template_store import save_template, load_template
from invoice_text_extractor import extract_text_from_pdf
from vendor_picker_ui import VendorPickerScreen
from box_labeling_ui import BoxLabelingScreen, render_pdf_page_as_image

COMPANY_NAME = "Test1"  # placeholder until company-selection step is built
PDF_PATH = "sample_data/inv1.pdf"
PAGE_NUMBER = 0


def start_box_labeling(vendor_key: str):
    """
    Called once a vendor has been selected. Ensures the party ledger is
    set (it's always the same as the picked vendor ledger — no separate
    selection step needed), then loads the invoice page and opens the
    box-labeling screen.
    """
    existing_template = load_template(vendor_key)
    existing_fields = existing_template.fields if existing_template else {}

    # Save immediately so party_ledger is set even before any field box
    # is drawn — e.g. if this is a brand new vendor with zero boxes yet.
    save_template(vendor_key, existing_fields, party_ledger=vendor_key)

    extraction_result = extract_text_from_pdf(PDF_PATH)
    if not extraction_result.success or not extraction_result.pages:
        print("Could not extract PDF text:", extraction_result.error_message)
        return

    image = render_pdf_page_as_image(PDF_PATH, PAGE_NUMBER, scale=2.0)
    labeling_screen = BoxLabelingScreen(image, extraction_result.pages[0], vendor_key)
    labeling_screen.mainloop()

if __name__ == "__main__":
    picker = VendorPickerScreen(
        company_name=COMPANY_NAME,
        on_vendor_selected=start_box_labeling,
    )
    picker.mainloop()