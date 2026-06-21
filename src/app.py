"""
app.py

The real entry point for the application: ties together file selection,
vendor selection, box labeling (when needed), and the review/push screen
into one continuous flow.

Run this file to use the app, instead of running individual screens
standalone (main_flow.py, review_screen_ui.py, etc. remain as useful
test scripts, but app.py is the real product entry point going forward).
"""

import customtkinter as ctk
from tkinter import filedialog, simpledialog

from invoice_text_extractor import extract_text_from_pdf
from vendor_picker_ui import VendorPickerScreen
from vendor_template_store import load_template, save_template
from box_labeling_ui import BoxLabelingScreen, render_pdf_page_as_image
from review_screen_ui import ReviewScreen


def ask_for_company_name() -> str | None:
    """
    Simple startup prompt for the Tally company name. A proper
    company-selection screen (e.g. fetched from Tally's open companies)
    is a reasonable future improvement — this is the minimal version.
    """
    root = ctk.CTk()
    root.withdraw()  # we only want the dialog, not an empty window
    company_name = simpledialog.askstring(
        "Company Name", "Enter the exact Tally company name to use:",
    )
    root.destroy()
    return company_name.strip() if company_name else None


def ask_for_invoice_file() -> str | None:
    root = ctk.CTk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Select an invoice PDF",
        filetypes=[("PDF files", "*.pdf")],
    )
    root.destroy()
    return file_path if file_path else None


def run_app():
    company_name = ask_for_company_name()
    if not company_name:
        print("No company name entered. Exiting.")
        return

    pdf_path = ask_for_invoice_file()
    if not pdf_path:
        print("No invoice file selected. Exiting.")
        return

    def on_vendor_selected(vendor_key: str):
        # Ensure party ledger is set immediately, same as main_flow.py did.
        existing_template = load_template(vendor_key)
        existing_fields = existing_template.fields if existing_template else {}
        save_template(vendor_key, existing_fields, party_ledger=vendor_key)

        has_template = existing_template is not None and len(existing_template.fields) > 0

        if has_template:
            # Repeat vendor with a saved layout — go straight to review.
            open_review_screen(company_name, vendor_key, pdf_path)
        else:
            # First-time vendor (or no fields labeled yet) — label first.
            open_labeling_screen(company_name, vendor_key, pdf_path)

    picker = VendorPickerScreen(company_name=company_name, on_vendor_selected=on_vendor_selected)
    picker.mainloop()


def open_labeling_screen(company_name: str, vendor_key: str, pdf_path: str):
    extraction_result = extract_text_from_pdf(pdf_path)
    if not extraction_result.success or not extraction_result.pages:
        print("Could not extract PDF text:", extraction_result.error_message)
        return

    image = render_pdf_page_as_image(pdf_path, page_number=0, scale=2.0)
    labeling_screen = BoxLabelingScreen(image, extraction_result.pages[0], vendor_key)

    # When the labeling window is closed, proceed to the review screen.
    # CustomTkinter doesn't have a built-in "on close, do X" hook beyond
    # the window protocol, so we use that directly.
    def on_labeling_closed():
        labeling_screen.destroy()
        open_review_screen(company_name, vendor_key, pdf_path)

    labeling_screen.protocol("WM_DELETE_WINDOW", on_labeling_closed)
    labeling_screen.mainloop()


def open_review_screen(company_name: str, vendor_key: str, pdf_path: str):
    def on_edit_template():
        open_labeling_screen(company_name, vendor_key, pdf_path)

    review = ReviewScreen(
        company_name=company_name, vendor_key=vendor_key, pdf_path=pdf_path,
        on_edit_template=on_edit_template,
    )
    review.mainloop()


if __name__ == "__main__":
    run_app()