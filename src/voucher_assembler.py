"""
voucher_assembler.py

Combines a vendor's saved template, the company's tax/purchase ledger
mapping, and the actual text read from an invoice's labeled boxes into
the exact inputs tally_bridge.push_voucher() expects.

This module does NOT talk to Tally directly and does NOT push anything —
it only assembles data. Pushing remains tally_bridge's job, and a
review step (not yet built) sits between this and any actual push.

Fails loudly via AssemblyError when required data is missing, rather
than silently producing an incomplete or wrong voucher.
"""

import re
from dataclasses import dataclass

from invoice_text_extractor import PageExtractionResult
from box_text_reader import read_text_in_box, Box
from vendor_template_store import load_template, FieldBox
from company_ledger_mapping_store import load_company_mapping, MAPPABLE_FIELDS
from tally_bridge import LedgerLine

# Maps the field names used in box-labeling (box_labeling_ui.py's
# FIXED_FIELDS) to the field names used in the company ledger mapping
# (company_ledger_mapping_store.py's MAPPABLE_FIELDS). These lists were
# built independently and happen to already match exactly for the
# amount fields, but this mapping is kept explicit rather than assumed,
# so a future rename in either place doesn't silently break assembly.
BOX_FIELD_TO_MAPPABLE_FIELD = {
    "Taxable Value": "Taxable Value",
    "CGST Amount": "CGST Amount",
    "SGST Amount": "SGST Amount",
    "IGST Amount": "IGST Amount",
}

# A purchase voucher needs a debit somewhere to balance the credit to
# the party. We assume Taxable Value is always the debit-side purchase
# amount; tax amounts (CGST/SGST/IGST) are also debited (input tax,
# the standard treatment for a purchase). This assumption is specific
# to PURCHASE vouchers — sales vouchers would need the signs flipped.
# Worth revisiting explicitly when we add sales voucher support.
DEBIT_FIELDS = {"Taxable Value", "CGST Amount", "SGST Amount", "IGST Amount"}


class AssemblyError(Exception):
    """Raised when a voucher cannot be assembled due to missing/invalid data."""
    pass


@dataclass
class AssembledVoucher:
    company_name: str
    voucher_type: str
    voucher_date_yyyymmdd: str
    party_ledger_name: str
    narration: str
    lines: list[LedgerLine]
    # Keeps the raw boxed text alongside the parsed amount, per field —
    # useful later for the review screen to show "we read X, parsed as Y".
    field_raw_text: dict[str, str]


def parse_amount_text(raw_text: str) -> float:
    """
    Converts boxed text like '₹ 89,898.00', '89,898.00', or '  1234  '
    into a float. Raises ValueError if the text doesn't contain a
    parsable number — this is intentional; a field that fails to parse
    should stop assembly, not silently become 0.0.
    """
    cleaned = raw_text.strip()
    cleaned = cleaned.replace("₹", "").replace(",", "").strip()

    # Keep only digits, one decimal point, and a leading minus if present.
    match = re.search(r"-?\d+(\.\d+)?", cleaned)
    if not match:
        raise ValueError(f"Could not parse a number from: '{raw_text}'")

    return float(match.group(0))


def _convert_field_date_to_yyyymmdd(raw_date_text: str) -> str:
    """
    Converts a boxed date like '1-Jun-26' into Tally's required
    YYYYMMDD format. Supports the common 'D-Mon-YY' style seen in our
    sample invoice. Raises ValueError for unrecognized formats — this
    is a known narrow point that will need broadening once we see more
    real-world date formats.
    """
    from datetime import datetime

    raw_date_text = raw_date_text.strip()
    known_formats = ["%d-%b-%y", "%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y"]

    for fmt in known_formats:
        try:
            parsed = datetime.strptime(raw_date_text, fmt)
            return parsed.strftime("%Y%m%d")
        except ValueError:
            continue

    raise ValueError(
        f"Could not parse date '{raw_date_text}' — supported formats: "
        "D-Mon-YY, D-Mon-YYYY, D/M/YYYY, D-M-YYYY"
    )


def assemble_purchase_voucher(
    company_name: str,
    vendor_key: str,
    page: PageExtractionResult,
) -> AssembledVoucher:
    """
    Builds an AssembledVoucher from a vendor's saved template and the
    invoice page's extracted words. Currently supports PURCHASE
    vouchers only (debit side: Taxable Value + tax amounts; credit
    side: the party ledger).
    """
    template = load_template(vendor_key)
    if template is None:
        raise AssemblyError(f"No saved template found for vendor '{vendor_key}'.")

    if not template.party_ledger:
        raise AssemblyError(f"Vendor '{vendor_key}' has no party ledger set.")

    company_mapping = load_company_mapping(company_name)
    if company_mapping is None:
        raise AssemblyError(
            f"No ledger mapping configured for company '{company_name}'. "
            "Set this up in the company mapping screen first."
        )

    missing_mappings = [f for f in MAPPABLE_FIELDS if f not in company_mapping]
    if missing_mappings:
        raise AssemblyError(
            f"Company ledger mapping is incomplete, missing: {', '.join(missing_mappings)}"
        )

    field_raw_text: dict[str, str] = {}
    for field_name, box in template.fields.items():
        pdf_box = Box(x0=box.x0, x1=box.x1, top=box.top, bottom=box.bottom)
        field_raw_text[field_name] = read_text_in_box(page, pdf_box)

    # --- Invoice number / date (metadata, not ledger lines) ---
    invoice_number = field_raw_text.get("Invoice Number", "").strip()
    raw_date = field_raw_text.get("Date", "").strip()
    if not raw_date:
        raise AssemblyError("Date field box was not labeled, or captured no text.")
    voucher_date = _convert_field_date_to_yyyymmdd(raw_date)

    # --- Amount fields → LedgerLine objects ---
    lines: list[LedgerLine] = []
    total_debit = 0.0

    for box_field_name, mappable_field_name in BOX_FIELD_TO_MAPPABLE_FIELD.items():
        raw_text = field_raw_text.get(box_field_name, "").strip()
        if not raw_text:
            # Not every invoice will have every tax field (e.g. no IGST
            # on an intra-state purchase) — skip fields that simply
            # weren't boxed/found, rather than erroring.
            continue

        amount = parse_amount_text(raw_text)
        ledger_name = company_mapping[mappable_field_name]

        lines.append(LedgerLine(
            ledger_name=ledger_name,
            amount=amount,
            is_debit=box_field_name in DEBIT_FIELDS,
        ))
        total_debit += amount

    if not lines:
        raise AssemblyError(
            "No amount fields (Taxable Value, CGST, SGST, IGST) produced any "
            "data — nothing to post."
        )

    # --- Party ledger line (credit side, balances the debits) ---
    lines.append(LedgerLine(
        ledger_name=template.party_ledger,
        amount=total_debit,
        is_debit=False,
    ))

    narration = f"Invoice {invoice_number}" if invoice_number else "Invoice (number not captured)"

    return AssembledVoucher(
        company_name=company_name,
        voucher_type="Purchase",
        voucher_date_yyyymmdd=voucher_date,
        party_ledger_name=template.party_ledger,
        narration=narration,
        lines=lines,
        field_raw_text=field_raw_text,
    )