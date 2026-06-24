"""
vendor_identity.py

Determines which vendor a new invoice belongs to, so the correct saved
template (from vendor_template_store.py) can be applied.

Strategy:
1. Look for a GSTIN on the page (reliable, fixed format) — if found,
   use it directly as the vendor_key.
2. If no GSTIN is found/extracted, fall back to fuzzy name matching
   against vendors we already have templates for.
3. If neither produces a confident match, return an "uncertain" result
   rather than guessing — the caller should ask the user to confirm or
   pick "this is a new vendor" instead of silently applying the wrong
   template.

This module deliberately does NOT try to be clever about layout/position
the way the old field guesser did — it works on whatever raw text is on
the page, since vendor identity doesn't depend on a specific invoice
layout the way field extraction does.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from invoice_text_extractor import PageExtractionResult
from vendor_template_store import list_known_vendors

# Standard GSTIN format: 15 characters —
# 2 digits (state code) + 10 chars (PAN) + 1 digit (entity number) +
# 1 char ('Z' by default) + 1 checksum character.
GSTIN_PATTERN = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]Z[A-Z\d]\b")

# Below this similarity score (0.0 to 1.0), we don't trust a name match
# enough to auto-apply a template — the caller should ask the user.
NAME_MATCH_CONFIDENCE_THRESHOLD = 0.82


@dataclass
class VendorIdentityResult:
    status: str  # "matched_by_gstin", "matched_by_name", "uncertain", "new_vendor"
    vendor_key: str | None
    matched_existing_vendor: str | None = None  # which known vendor this was matched to, if any
    candidates: list[str] | None = None  # possible matches, shown when status is "uncertain"


def _find_gstin_in_text(full_text: str) -> str | None:
    match = GSTIN_PATTERN.search(full_text.upper())
    return match.group(0) if match else None


def _best_name_match(candidate_name: str, known_vendors: list[str]) -> tuple[str | None, float]:
    """
    Returns the known vendor name most similar to candidate_name, and
    its similarity score (0.0 to 1.0). Uses simple sequence-matching
    rather than anything more elaborate — vendor names are short, so
    this is fast and good enough; we can swap in a smarter library
    later if real-world testing shows it's not.
    """
    best_match = None
    best_score = 0.0

    for known in known_vendors:
        score = SequenceMatcher(None, candidate_name.lower(), known.lower()).ratio()
        if score > best_score:
            best_score = score
            best_match = known

    return best_match, best_score


def identify_vendor(page: PageExtractionResult, extracted_party_name: str | None = None) -> VendorIdentityResult:
    """
    Attempts to identify which known vendor (if any) this invoice belongs to.

    extracted_party_name: optionally pass the party name already read
    from a box (via box_text_reader), if available — this is more
    reliable than re-deriving it from raw text, since the user-drawn
    box is exact. If not provided, name matching is skipped and we
    rely on GSTIN only.
    """
    gstin = _find_gstin_in_text(page.full_text)
    if gstin:
        return VendorIdentityResult(status="matched_by_gstin", vendor_key=gstin)

    known_vendors = list_known_vendors()

    if not known_vendors:
        # Nothing to match against yet — definitely a new vendor.
        return VendorIdentityResult(status="new_vendor", vendor_key=None)

    if not extracted_party_name:
        # No GSTIN, no name to compare — we genuinely can't tell.
        return VendorIdentityResult(
            status="uncertain", vendor_key=None, candidates=known_vendors,
        )

    best_match, score = _best_name_match(extracted_party_name, known_vendors)

    if score >= NAME_MATCH_CONFIDENCE_THRESHOLD:
        return VendorIdentityResult(
            status="matched_by_name",
            vendor_key=best_match,
            matched_existing_vendor=best_match,
        )

    # Some similarity, but not enough to trust automatically — let the
    # user decide rather than silently picking a possibly-wrong template.
    close_candidates = [
        v for v in known_vendors
        if SequenceMatcher(None, extracted_party_name.lower(), v.lower()).ratio() >= 0.5
    ]

    if close_candidates:
        return VendorIdentityResult(
            status="uncertain", vendor_key=None, candidates=close_candidates,
        )

    return VendorIdentityResult(status="new_vendor", vendor_key=extracted_party_name)