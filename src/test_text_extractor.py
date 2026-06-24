from invoice_text_extractor import extract_text_from_pdf

result = extract_text_from_pdf("sample_data/inv1.pdf")

print("Success:", result.success)
print("Has usable text:", result.has_usable_text)
print("Error (if any):", result.error_message)
print("\n--- FULL TEXT ---")
print(result.full_text)

print("\n--- FIRST 15 WORDS WITH POSITIONS (page 1) ---")
if result.pages:
    for word in result.pages[0].words[:15]:
        print(f"'{word.text}'  x0={word.x0:.1f} top={word.top:.1f}")