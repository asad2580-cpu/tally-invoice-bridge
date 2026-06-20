from company_ledger_mapping_store import (
    save_company_mapping,
    load_company_mapping,
    is_mapping_complete,
    list_companies_with_mappings,
    MAPPABLE_FIELDS,
)

COMPANY_NAME = "Test1"

print("=== Fields that need mapping ===")
print(MAPPABLE_FIELDS)

print("\n=== Before saving anything ===")
print("Mapping (should be None):", load_company_mapping(COMPANY_NAME))
print("Is complete (should be False):", is_mapping_complete(COMPANY_NAME))

print("\n=== Saving a PARTIAL mapping (missing IGST) ===")
partial = {
    "Taxable Value": "Purchase Account",
    "CGST Amount": "Input CGST",
    "SGST Amount": "Input SGST",
}
save_company_mapping(COMPANY_NAME, partial)
print("Is complete (should be False):", is_mapping_complete(COMPANY_NAME))

print("\n=== Saving the COMPLETE mapping ===")
complete = {
    "Taxable Value": "Purchase Account",
    "CGST Amount": "Input CGST",
    "SGST Amount": "Input SGST",
    "IGST Amount": "Input IGST",
}
save_company_mapping(COMPANY_NAME, complete)
print("Is complete (should be True):", is_mapping_complete(COMPANY_NAME))

print("\n=== Loading it back ===")
loaded = load_company_mapping(COMPANY_NAME)
for field, ledger in loaded.items():
    print(f"  {field} -> {ledger}")

print("\n=== Companies with mappings ===")
print(list_companies_with_mappings())