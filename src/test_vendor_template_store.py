from vendor_template_store import (
    save_template,
    load_template,
    list_known_vendors,
    delete_template,
    FieldBox,
)

VENDOR_KEY = "Sharma Traders"  # in real use, this would be a GSTIN when available

print("=== Before saving anything ===")
print("Known vendors:", list_known_vendors())
print("Load (should be None):", load_template(VENDOR_KEY))

print("\n=== Saving a template ===")
fields = {
    "invoice_number": FieldBox(x0=276.8, x1=290.0, top=59.0, bottom=66.0),
    "date": FieldBox(x0=391.4, x1=430.0, top=59.0, bottom=66.0),
    "party_name": FieldBox(x0=38.8, x1=120.0, top=232.1, bottom=240.0),
    "total_amount": FieldBox(x0=470.0, x1=520.0, top=560.3, bottom=568.0),
}
success = save_template(VENDOR_KEY, fields)
print("Save success:", success)

print("\n=== Loading it back ===")
loaded = load_template(VENDOR_KEY)
print("Vendor key:", loaded.vendor_key)
print("Last updated:", loaded.last_updated_utc)
for name, box in loaded.fields.items():
    print(f"  {name}: x0={box.x0}, top={box.top}")

print("\n=== Known vendors now ===")
print(list_known_vendors())

print("\n=== Simulating a correction (overwrite total_amount) ===")
fields["total_amount"] = FieldBox(x0=475.0, x1=525.0, top=560.3, bottom=568.0)
save_template(VENDOR_KEY, fields)
loaded_again = load_template(VENDOR_KEY)
print("New total_amount x0:", loaded_again.fields["total_amount"].x0)

print("\n=== Deleting the template ===")
print("Delete success:", delete_template(VENDOR_KEY))
print("Load after delete (should be None):", load_template(VENDOR_KEY))