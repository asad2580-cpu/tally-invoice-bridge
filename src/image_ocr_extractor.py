"""
image_ocr_extractor.py

Runs Tesseract OCR on an image (a scanned/photographed invoice) and
returns the result in the SAME shape as invoice_text_extractor.py's
PdfExtractionResult/PageExtractionResult — specifically, a list of
WordBox objects with text + position.

This lets every downstream module (box_text_reader, voucher_assembler,
the labeling UI) work identically regardless of whether the words came
from a text-layer PDF or from OCR on an image. The only difference
callers need to be aware of: these coordinates are in IMAGE PIXELS,
not PDF points, since there's no PDF page involved at all.
"""

import pytesseract
from PIL import Image
from dataclasses import dataclass, field

from invoice_text_extractor import WordBox, PageExtractionResult

# Tesseract's confidence score (0-100) below which we discard a "word" —
# very low confidence detections are often noise (stray marks, table
# lines misread as characters) rather than real text.
MIN_CONFIDENCE = 30


@dataclass
class ImageExtractionResult:
    success: bool
    has_usable_text: bool
    page: PageExtractionResult | None = None
    error_message: str = ""


def extract_text_from_image(image_path: str) -> ImageExtractionResult:
    """
    Runs OCR on the given image file and returns word-level text with
    pixel-coordinate bounding boxes, in the same WordBox shape used
    throughout the rest of the app.
    """
    try:
        image = Image.open(image_path)
    except Exception as e:
        return ImageExtractionResult(
            success=False, has_usable_text=False,
            error_message=f"Could not open image: {e}",
        )

    try:
        # image_to_data returns a dict of parallel lists: one entry per
        # detected text region, including words, lines, and blocks all
        # mixed together — we filter to keep only actual word-level
        # entries with real text.
        ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError:
        return ImageExtractionResult(
            success=False, has_usable_text=False,
            error_message=(
                "Tesseract is not installed or not on PATH. "
                "Install it from https://github.com/UB-Mannheim/tesseract/wiki "
                "and ensure its folder is added to your system PATH."
            ),
        )
    except Exception as e:
        return ImageExtractionResult(
            success=False, has_usable_text=False,
            error_message=f"OCR failed: {e}",
        )

    words: list[WordBox] = []
    full_text_parts: list[str] = []

    num_entries = len(ocr_data["text"])
    for i in range(num_entries):
        text = ocr_data["text"][i].strip()
        if not text:
            continue

        try:
            confidence = float(ocr_data["conf"][i])
        except (ValueError, TypeError):
            confidence = -1

        if confidence < MIN_CONFIDENCE:
            continue

        x = ocr_data["left"][i]
        y = ocr_data["top"][i]
        width = ocr_data["width"][i]
        height = ocr_data["height"][i]

        words.append(WordBox(
            text=text,
            x0=float(x),
            x1=float(x + width),
            top=float(y),
            bottom=float(y + height),
        ))
        full_text_parts.append(text)

    has_usable_text = len(words) > 0

    page = PageExtractionResult(
        page_number=1,
        full_text=" ".join(full_text_parts),
        words=words,
    )

    return ImageExtractionResult(success=True, has_usable_text=has_usable_text, page=page)