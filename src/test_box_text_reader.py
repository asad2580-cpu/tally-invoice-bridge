from invoice_text_extractor import extract_text_from_pdf
from box_text_reader import read_text_in_box, Box

result = extract_text_from_pdf("sample_data/inv1.pdf")
page = result.pages[0]

print("=== Reading text from known box positions ===\n")

test_cases = [
    ("Invoice number area", Box(x0=270, x1=300, top=55, bottom=65)),
    ("Date area", Box(x0=385, x1=440, top=55, bottom=65)),
    ("Party name area", Box(x0=35, x1=160, top=228, bottom=242)),
    ("Total amount area", Box(x0=440, x1=525, top=555, bottom=568)),
    ("Empty/off-target area", Box(x0=900, x1=950, top=900, bottom=920)),
]

for label, box in test_cases:
    text = read_text_in_box(page, box)
    print(f"{label}: '{text}'")