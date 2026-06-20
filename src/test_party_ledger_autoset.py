from vendor_template_store import load_template

VENDOR_KEY = "Sharma Traders"  # change this to whichever vendor you pick when testing

template = load_template(VENDOR_KEY)
if template:
    print(f"Vendor: {template.vendor_key}")
    print(f"Party ledger: {template.party_ledger}")
    print(f"Fields saved: {list(template.fields.keys())}")
else:
    print("No template found for this vendor yet.")