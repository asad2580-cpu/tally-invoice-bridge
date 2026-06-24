from invoice_text_extractor import extract_text_from_pdf
from invoice_field_guesser import guess_invoice_fields

result = extract_text_from_pdf("sample_data/inv1.pdf")

if not result.success or not result.pages:
    print("Extraction failed:", result.error_message)
else:
    guesses = guess_invoice_fields(result.pages[0])

    print("--- FIELD GUESSES ---")
    for field_name, guess in guesses.items():
        if guess.confidence == "found":
            print(f"{field_name}: '{guess.value}'  (at x0={guess.x0:.1f}, top={guess.top:.1f})")
        else:
            print(f"{field_name}: NOT FOUND")