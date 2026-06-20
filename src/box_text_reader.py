"""
box_text_reader.py

Given a box (in PDF point coordinates, matching invoice_text_extractor.py's
WordBox coordinate system) and a page's extracted words, returns the text
that falls inside that box.

This is the piece that turns "user drew a box on screen" into "we have
the actual value" — no label-guessing, no heuristics about rows/columns,
just: what text overlaps this region the user pointed at.
"""

from dataclasses import dataclass
from invoice_text_extractor import WordBox, PageExtractionResult


@dataclass
class Box:
    x0: float
    x1: float
    top: float
    bottom: float


def _word_overlaps_box(word: WordBox, box: Box, overlap_threshold: float = 0.5) -> bool:
    """
    Returns True if a word sufficiently overlaps the box, not just
    touches its edge. We require at least `overlap_threshold` (default
    50%) of the word's own area to fall inside the box, in both the
    horizontal and vertical direction. This avoids accidentally pulling
    in a neighboring word that just barely clips the box's edge.
    """
    # Horizontal overlap
    overlap_x0 = max(word.x0, box.x0)
    overlap_x1 = min(word.x1, box.x1)
    overlap_width = max(0.0, overlap_x1 - overlap_x0)
    word_width = max(word.x1 - word.x0, 0.01)  # avoid divide-by-zero on zero-width artifacts
    horizontal_ratio = overlap_width / word_width

    # Vertical overlap
    overlap_top = max(word.top, box.top)
    overlap_bottom = min(word.bottom, box.bottom)
    overlap_height = max(0.0, overlap_bottom - overlap_top)
    word_height = max(word.bottom - word.top, 0.01)
    vertical_ratio = overlap_height / word_height

    return horizontal_ratio >= overlap_threshold and vertical_ratio >= overlap_threshold


def read_text_in_box(page: PageExtractionResult, box: Box) -> str:
    """
    Returns the text found inside the given box, reading words in
    natural order (top-to-bottom, then left-to-right within a row) —
    this matters for boxes that span multiple words or even multiple
    lines (e.g. a multi-line party name).

    Returns an empty string if no words overlap the box sufficiently —
    this is a normal, expected outcome (e.g. user drew a box slightly
    off-target) and should be surfaced to the user as "nothing found
    here, try adjusting the box", not treated as an error.
    """
    matching_words = [w for w in page.words if _word_overlaps_box(w, box)]

    if not matching_words:
        return ""

    # Sort by row first (top), then by horizontal position (x0) within
    # each row, so multi-word/multi-line values read out correctly.
    matching_words.sort(key=lambda w: (round(w.top), w.x0))

    return " ".join(w.text for w in matching_words)