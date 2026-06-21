"""
Tests image_ocr_extractor.py against a rendered image of our sample
invoice (rendered from the PDF, same way the box-drawing UI does it) —
this is a stand-in for a real scanned image until a true sample is
available, but it proves the OCR mechanism itself works.
"""

import pypdfium2 as pdfium
from image_ocr_extractor import extract_text_from_image

PDF_PATH = "sample_data/inv1.pdf"
TEMP_IMAGE_PATH = "sample_data/inv1_rendered_for_ocr_test.png"

# Render the PDF page to an image file, simulating what a real scanned
# invoice file would look like as input to the OCR path.
pdf = pdfium.PdfDocument(PDF_PATH)
page = pdf[0]
bitmap = page.render(scale=2.0)
image = bitmap.to_pil()
image.save(TEMP_IMAGE_PATH)

print(f"Rendered test image saved to {TEMP_IMAGE_PATH}\n")

result = extract_text_from_image(TEMP_IMAGE_PATH)

print("Success:", result.success)
print("Has usable text:", result.has_usable_text)
print("Error (if any):", result.error_message)

if result.page:
    print(f"\nWords found: {len(result.page.words)}")
    print("\nFirst 15 words with positions:")
    for word in result.page.words[:15]:
        print(f"  '{word.text}'  x0={word.x0:.0f} top={word.top:.0f}")