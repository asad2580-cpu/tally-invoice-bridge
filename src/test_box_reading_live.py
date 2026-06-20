"""
Pass 1 of the box-drawing UI: draw a box, see the captured text live
on screen. No labeling or saving yet — just confirming the draw-and-read
feedback loop feels right before we add the rest.
"""

import customtkinter as ctk
from PIL import Image, ImageTk
import pypdfium2 as pdfium

from invoice_text_extractor import extract_text_from_pdf
from box_text_reader import read_text_in_box, Box

PDF_PATH = "sample_data/inv1.pdf"
PAGE_NUMBER = 0
RENDER_SCALE = 2.0


def render_pdf_page_as_image(pdf_path: str, page_number: int, scale: float) -> Image.Image:
    pdf = pdfium.PdfDocument(pdf_path)
    page = pdf[page_number]
    bitmap = page.render(scale=scale)
    return bitmap.to_pil()


class BoxReadingLiveDemo(ctk.CTk):
    def __init__(self, pil_image: Image.Image, page_data):
        super().__init__()

        self.title("Box Reading - Live Demo")
        self.page_data = page_data  # PageExtractionResult, used to read text inside boxes

        self.tk_image = ImageTk.PhotoImage(pil_image)

        # Layout: canvas on the left, a results panel on the right
        self.canvas = ctk.CTkCanvas(
            self,
            width=pil_image.width,
            height=pil_image.height,
            highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)

        results_panel = ctk.CTkFrame(self, width=300)
        results_panel.grid(row=0, column=1, sticky="ns", padx=10, pady=10)

        ctk.CTkLabel(
            results_panel, text="Captured text:",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", pady=(0, 5))

        self.result_label = ctk.CTkLabel(
            results_panel,
            text="(draw a box on the invoice)",
            wraplength=260,
            justify="left",
            text_color="gray",
        )
        self.result_label.pack(anchor="w")

        ctk.CTkLabel(
            results_panel, text="\nLast box (PDF points):",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", pady=(15, 5))

        self.coords_label = ctk.CTkLabel(
            results_panel, text="-", justify="left", text_color="gray",
        )
        self.coords_label.pack(anchor="w")

        self.start_x = None
        self.start_y = None
        self.current_rectangle_id = None

        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

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

        pdf_box = Box(
            x0=left / RENDER_SCALE,
            x1=right / RENDER_SCALE,
            top=top / RENDER_SCALE,
            bottom=bottom / RENDER_SCALE,
        )

        captured_text = read_text_in_box(self.page_data, pdf_box)

        if captured_text:
            self.result_label.configure(text=f"'{captured_text}'", text_color="white")
        else:
            self.result_label.configure(
                text="(nothing found here — try redrawing the box)",
                text_color="orange",
            )

        self.coords_label.configure(
            text=f"x0={pdf_box.x0:.1f}, top={pdf_box.top:.1f}\n"
                 f"x1={pdf_box.x1:.1f}, bottom={pdf_box.bottom:.1f}",
            text_color="gray",
        )


if __name__ == "__main__":
    extraction_result = extract_text_from_pdf(PDF_PATH)
    if not extraction_result.success or not extraction_result.pages:
        print("Could not extract PDF text:", extraction_result.error_message)
    else:
        image = render_pdf_page_as_image(PDF_PATH, PAGE_NUMBER, RENDER_SCALE)
        app = BoxReadingLiveDemo(image, extraction_result.pages[0])
        app.mainloop()