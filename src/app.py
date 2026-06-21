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
from image_ocr_extractor import extract_text_from_image
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
        title="Select an invoice (PDF or image)",
        filetypes=[
            ("Invoice files", "*.pdf *.jpg *.jpeg *.png"),
            ("PDF files", "*.pdf"),
            ("Image files", "*.jpg *.jpeg *.png"),
        ],
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

def load_invoice_page_and_image(file_path: str):
    """
    Given an invoice file (PDF or image), returns (page_data, pil_image,
    coordinate_scale) using whichever extraction path is appropriate:
    - PDF with a real text layer: pdfplumber extraction, rendered image
      for display, with RENDER_SCALE conversion between pixel display
      and PDF-point coordinates.
    - PDF with no usable text layer (scanned), or a plain image file:
      OCR extraction, where the image IS the coordinate space directly
      (scale = 1.0, no conversion needed).

    Returns (None, None, None) if extraction fails entirely.
    """
    lower_path = file_path.lower()

    if lower_path.endswith(".pdf"):
        pdf_result = extract_text_from_pdf(file_path)
        if pdf_result.success and pdf_result.has_usable_text:
            image = render_pdf_page_as_image(file_path, page_number=0, scale=2.0)
            return pdf_result.pages[0], image, 2.0

        # Fall back to OCR: render the PDF page as an image, then OCR it.
        print("No usable text layer found in PDF \u2014 falling back to OCR.")
        image = render_pdf_page_as_image(file_path, page_number=0, scale=2.0)
        temp_image_path = file_path + "_ocr_temp.png"
        image.save(temp_image_path)
        ocr_result = extract_text_from_image(temp_image_path)
        if ocr_result.success and ocr_result.page:
            return ocr_result.page, image, 1.0
        print("OCR fallback also failed:", ocr_result.error_message)
        return None, None, None

    else:
        # Plain image file (jpg, png, etc.) \u2014 OCR directly, no scaling.
        ocr_result = extract_text_from_image(file_path)
        if not ocr_result.success or not ocr_result.page:
            print("OCR failed:", ocr_result.error_message)
            return None, None, None
        from PIL import Image
        image = Image.open(file_path)
        return ocr_result.page, image, 1.0


def open_labeling_screen(company_name: str, vendor_key: str, pdf_path: str):
    page_data, image, scale = load_invoice_page_and_image(pdf_path)
    if page_data is None:
        print("Could not extract invoice data from this file.")
        return

    labeling_screen = BoxLabelingScreen(image, page_data, vendor_key, render_scale=scale)

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