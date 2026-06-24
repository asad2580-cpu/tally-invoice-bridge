from invoice_text_extractor import PageExtractionResult, WordBox
from vendor_identity import identify_vendor
from vendor_template_store import save_template, delete_template, FieldBox

# Clean up any leftover test data from earlier runs first.
delete_template("Sharma Traders")

def fake_page(text: str) -> PageExtractionResult:
    return PageExtractionResult(page_number=1, full_text=text, words=[])

print("=== No known vendors yet, no GSTIN ===")
result = identify_vendor(fake_page("Invoice from Sharma Traders"), extracted_party_name="Sharma Traders")
print(result)

print("\n=== Now save a template for Sharma Traders, then test matching ===")
save_template("Sharma Traders", {"date": FieldBox(0, 0, 0, 0)})

print("\n--- Exact name match ---")
result = identify_vendor(fake_page("some invoice text"), extracted_party_name="Sharma Traders")
print(result)

print("\n--- Slightly different name (should still match, OCR-style noise) ---")
result = identify_vendor(fake_page("some invoice text"), extracted_party_name="Sharma Tradres")
print(result)

print("\n--- Very different name (should be new_vendor or uncertain) ---")
result = identify_vendor(fake_page("some invoice text"), extracted_party_name="ABC Enterprises")
print(result)

print("\n--- GSTIN present (should win over name matching entirely) ---")
result = identify_vendor(
    fake_page("Company GSTIN: 07ABCDE1234F1Z5 some other text"),
    extracted_party_name="Totally Different Name Inc",
)
print(result)

# Cleanup
delete_template("Sharma Traders")