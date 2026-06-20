"""
Proof-of-concept: render a PDF page as an image, display it in a window,
and let the user draw a single rectangle with the mouse. Prints the
rectangle's coordinates on release.

This is throwaway/diagnostic — confirms the core interaction works
before we build the real labeling/saving UI on top of it.
"""

import customtkinter as ctk
from PIL import Image, ImageTk
import pypdfium2 as pdfium

PDF_PATH = "sample_data/inv1.pdf"
PAGE_NUMBER = 0  # pypdfium2 uses 0-based page indexing
RENDER_SCALE = 2.0  # higher = sharper image, but larger window


def render_pdf_page_as_image(pdf_path: str, page_number: int, scale: float) -> Image.Image:
    pdf = pdfium.PdfDocument(pdf_path)
    page = pdf[page_number]
    bitmap = page.render(scale=scale)
    return bitmap.to_pil()


class BoxDrawingPOC(ctk.CTk):
    def __init__(self, pil_image: Image.Image):
        super().__init__()

        self.title("Box Drawing Proof of Concept")

        # Keep a reference to the PhotoImage — Tkinter will silently fail
        # to display the image if this gets garbage collected.
        self.tk_image = ImageTk.PhotoImage(pil_image)

        self.canvas = ctk.CTkCanvas(
            self,
            width=pil_image.width,
            height=pil_image.height,
            highlightthickness=0,
        )
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)

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
        x0, y0 = self.start_x, self.start_y
        x1, y1 = event.x, event.y
        left, right = sorted([x0, x1])
        top, bottom = sorted([y0, y1])

        # Convert canvas pixel coordinates back to PDF point coordinates,
        # so this box can be directly compared against pdfplumber's
        # word positions (which are in PDF points, not rendered pixels).
        pdf_x0 = left / RENDER_SCALE
        pdf_x1 = right / RENDER_SCALE
        pdf_top = top / RENDER_SCALE
        pdf_bottom = bottom / RENDER_SCALE

        print(f"Canvas pixels: x0={left}, top={top}, x1={right}, bottom={bottom}")
        print(f"PDF points:    x0={pdf_x0:.1f}, top={pdf_top:.1f}, x1={pdf_x1:.1f}, bottom={pdf_bottom:.1f}")
        print()


if __name__ == "__main__":
    image = render_pdf_page_as_image(PDF_PATH, PAGE_NUMBER, RENDER_SCALE)
    app = BoxDrawingPOC(image)
    app.mainloop()