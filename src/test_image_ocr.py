"""
Tests image_ocr_extractor.py against a real, messy/photographed invoice
sample — a genuine stress test of OCR accuracy, not just mechanism.
"""

from image_ocr_extractor import extract_text_from_image

IMAGE_PATH = "sample_data/inv3.jpg"

result = extract_text_from_image(IMAGE_PATH)

print("Success:", result.success)
print("Has usable text:", result.has_usable_text)
print("Error (if any):", result.error_message)

if result.page:
    print(f"\nWords found: {len(result.page.words)}")
    print("\nAll words with positions:")
    for word in result.page.words:
        print(f"  '{word.text}'  x0={word.x0:.0f} top={word.top:.0f}")

    print("\n--- FULL TEXT (joined) ---")
    print(result.page.full_text)