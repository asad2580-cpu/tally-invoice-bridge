"""
Pass 2 of the box-drawing UI: draw a box, label it from the fixed field
list, and save it into the vendor template store.

This screen is responsible for ONE thing: capturing fixed-field box
positions for a vendor (Invoice No., Date, Taxable Value, CGST, SGST,
IGST, Party Name/GSTIN). Ledger selection (party ledger, tax-to-ledger
mapping) is handled by separate screens, not here.
"""

import customtkinter as ctk
from PIL import Image, ImageTk
import pypdfium2 as pdfium

from invoice_text_extractor import extract_text_from_pdf
from box_text_reader import read_text_in_box, Box
from vendor_template_store import save_template, load_template, FieldBox

PDF_PATH = "sample_data/inv1.pdf"
PAGE_NUMBER = 0
RENDER_SCALE = 2.0
VENDOR_KEY = "Sharma Traders"  # placeholder until vendor-identity matching exists

# The fixed list of fields this screen can label boxes with.
# This list is owned by us, not fetched from Tally.
FIXED_FIELDS = [
    "Invoice Number",
    "Date",
    "Party Name",
    "Party GSTIN",
    "Taxable Value",
    "CGST Amount",
    "SGST Amount",
    "IGST Amount",
]


def render_pdf_page_as_image(pdf_path: str, page_number: int, scale: float) -> Image.Image:
    pdf = pdfium.PdfDocument(pdf_path)
    page = pdf[page_number]
    bitmap = page.render(scale=scale)
    return bitmap.to_pil()


class BoxLabelingScreen(ctk.CTk):
    def __init__(self, pil_image: Image.Image, page_data, vendor_key: str):
        super().__init__()

        self.title("Label Invoice Fields")
        self.page_data = page_data
        self.vendor_key = vendor_key

        # In-memory working copy of this vendor's field boxes. Synced to
        # disk (via save_template) every time a box is confirmed, so
        # progress is never lost even if the app closes unexpectedly.
        self.field_boxes: dict[str, FieldBox] = {}

        existing = load_template(vendor_key)
        if existing:
            self.field_boxes = dict(existing.fields)

        self.tk_image = ImageTk.PhotoImage(pil_image)

        self.canvas = ctk.CTkCanvas(
            self, width=pil_image.width, height=pil_image.height,
            highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)

        # Track rectangle IDs per field name, so we can redraw saved
        # boxes from a loaded template and update them when relabeled.
        self.rectangle_ids: dict[str, int] = {}
        self._redraw_existing_boxes()

        side_panel = ctk.CTkFrame(self, width=320)
        side_panel.grid(row=0, column=1, sticky="ns", padx=10, pady=10)

        ctk.CTkLabel(
            side_panel, text=f"Vendor: {vendor_key}",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(side_panel, text="Captured text:").pack(anchor="w")
        self.captured_text_label = ctk.CTkLabel(
            side_panel, text="(draw a box)", wraplength=280,
            justify="left", text_color="gray",
        )
        self.captured_text_label.pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(side_panel, text="Label this box as:").pack(anchor="w")
        self.field_dropdown = ctk.CTkOptionMenu(side_panel, values=FIXED_FIELDS)
        self.field_dropdown.pack(anchor="w", pady=(0, 10), fill="x")
        self.field_dropdown.set(FIXED_FIELDS[0])

        self.confirm_button = ctk.CTkButton(
            side_panel, text="Confirm & Save", command=self._on_confirm,
            state="disabled",
        )
        self.confirm_button.pack(anchor="w", pady=(0, 15), fill="x")

        ctk.CTkLabel(
            side_panel, text="Labeled so far:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w")
        self.progress_label = ctk.CTkLabel(
            side_panel, text="", justify="left", wraplength=280,
        )
        self.progress_label.pack(anchor="w", pady=(5, 0))
        self._refresh_progress_label()

        self.start_x = None
        self.start_y = None
        self.current_rectangle_id = None
        self.pending_pdf_box: Box | None = None

        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

    def _redraw_existing_boxes(self):
        for field_name, box in self.field_boxes.items():
            rect_id = self.canvas.create_rectangle(
                box.x0 * RENDER_SCALE, box.top * RENDER_SCALE,
                box.x1 * RENDER_SCALE, box.bottom * RENDER_SCALE,
                outline="green", width=2,
            )
            self.rectangle_ids[field_name] = rect_id

    def _refresh_progress_label(self):
        if not self.field_boxes:
            self.progress_label.configure(text="(none yet)")
            return
        lines = [f"\u2713 {name}" for name in self.field_boxes.keys()]
        self.progress_label.configure(text="\n".join(lines))

    def _on_mouse_down(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.current_rectangle_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="red", width=2,
        )

    def _on_mouse_drag(self, event):
        self.canvas.coords(
            self.current_rectangle_id,
            self.start_x, self.start_y, event.x, event.y,
        )

    def _on_mouse_up(self, event):
        left, right = sorted([self.start_x, event.x])
        top, bottom = sorted([self.start_y, event.y])

        self.pending_pdf_box = Box(
            x0=left / RENDER_SCALE, x1=right / RENDER_SCALE,
            top=top / RENDER_SCALE, bottom=bottom / RENDER_SCALE,
        )

        captured_text = read_text_in_box(self.page_data, self.pending_pdf_box)
        if captured_text:
            self.captured_text_label.configure(text=f"'{captured_text}'", text_color="white")
        else:
            self.captured_text_label.configure(
                text="(nothing found — try redrawing)", text_color="orange",
            )

        self.confirm_button.configure(state="normal")

    def _on_confirm(self):
        if self.pending_pdf_box is None:
            return

        field_name = self.field_dropdown.get()

        # If this field was already labeled before, remove its old
        # rectangle from the canvas before drawing the new one.
        if field_name in self.rectangle_ids:
            self.canvas.delete(self.rectangle_ids[field_name])

        self.field_boxes[field_name] = FieldBox(
            x0=self.pending_pdf_box.x0, x1=self.pending_pdf_box.x1,
            top=self.pending_pdf_box.top, bottom=self.pending_pdf_box.bottom,
        )

        # Turn the just-confirmed box green, to visually distinguish
        # "saved" boxes from the in-progress red one.
        rect_id = self.canvas.create_rectangle(
            self.pending_pdf_box.x0 * RENDER_SCALE, self.pending_pdf_box.top * RENDER_SCALE,
            self.pending_pdf_box.x1 * RENDER_SCALE, self.pending_pdf_box.bottom * RENDER_SCALE,
            outline="green", width=2,
        )
        self.rectangle_ids[field_name] = rect_id
        self.canvas.delete(self.current_rectangle_id)

        save_template(self.vendor_key, self.field_boxes)

        self._refresh_progress_label()
        self.confirm_button.configure(state="disabled")
        self.pending_pdf_box = None


if __name__ == "__main__":
    extraction_result = extract_text_from_pdf(PDF_PATH)
    if not extraction_result.success or not extraction_result.pages:
        print("Could not extract PDF text:", extraction_result.error_message)
    else:
        image = render_pdf_page_as_image(PDF_PATH, PAGE_NUMBER, RENDER_SCALE)
        app = BoxLabelingScreen(image, extraction_result.pages[0], VENDOR_KEY)
        app.mainloop()