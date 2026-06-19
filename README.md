# Tally Invoice Bridge

A free, fully local desktop tool that reads sale/purchase invoices (image or PDF),
helps you confirm the extracted details, maps them to **existing** ledgers in
TallyPrime (no auto-creation), and pushes the voucher directly into Tally via
its local API.

## Why this exists

Small businesses and accountants often get invoices in inconsistent, sometimes
handwritten "desi style" formats. This tool does not promise perfect automatic
extraction — instead it does its best guess, shows you exactly what it found,
and makes correcting it fast. It remembers corrections per vendor, so invoices
from a vendor you've corrected before get easier over time.

## Core principles (do not violate these without updating this doc)

1. **No ledger auto-creation.** Vouchers are only pushed to ledgers that
   already exist in the user's TallyPrime company. If a ledger doesn't exist,
   the user is told clearly — nothing is silently created.
2. **Zero running cost.** Everything runs on the user's own machine. No
   servers, no databases we host, no paid APIs required for core functionality.
3. **Nothing is pushed to Tally without an explicit review step.** Every
   invoice produces a reviewable record (in-app, backed by a JSON file)
   before any data reaches Tally.
4. **Local data stays local.** Vendor templates, extracted invoice data, and
   push logs live on the user's machine, never uploaded anywhere.

## Architecture (high level)

```
Invoice (image/PDF)
      |
      v
  OCR + field guesser  --(uses)-->  vendor template memory (local)
      |
      v
  Correction UI (user fixes any wrong fields)
      |
      v
  Review record (JSON) --- shown in-app for final check
      |
      v
  Tally Bridge module --(HTTP/XML)--> TallyPrime local server (localhost:9000)
      |
      v
  Push result parsed back into the review record
```

## Status

🔧 Step 1 of 8: project scaffolding. Nothing functional yet.

See `docs/` for build-step notes as we go.

## Requirements (once functional)

- TallyPrime running locally with its HTTP/XML server enabled
  (Gateway of Tally → F1 (Help) → Settings → Connectivity, or via the
  `tally.ini` configuration — exact steps documented in `docs/` once we
  reach the Tally Bridge step)
- Python 3.11+
- Tesseract OCR installed on the system (added when we reach the OCR step)