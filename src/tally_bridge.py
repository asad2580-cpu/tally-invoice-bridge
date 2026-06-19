"""
tally_bridge.py

The single module responsible for ALL communication with a locally running
TallyPrime instance over its HTTP/XML server.

This module is intentionally the only place in the whole app that talks to
Tally directly. Every other part of the app (UI, OCR, review screen) should
go through the functions here rather than building Tally XML itself.

Core guarantee enforced by this module:
    No ledger is ever auto-created. Every push validates that all referenced
    ledgers already exist in Tally (via get_ledger_names) BEFORE attempting
    to write a voucher. Tally's own server also rejects unknown ledgers
    independently, so this is defense in depth, not the only safeguard.
"""

import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

TALLY_URL = "http://localhost:9000"
REQUEST_TIMEOUT_SECONDS = 10


# ---------------------------------------------------------------------------
# Result types
#
# Using small dataclasses instead of plain dicts/tuples so calling code
# (the UI, later) gets clear attribute names instead of guessing what
# result[0] or result["data"] means.
# ---------------------------------------------------------------------------

@dataclass
class LedgerFetchResult:
    success: bool
    ledger_names: list[str] = field(default_factory=list)
    error_message: str = ""


@dataclass
class VoucherPushResult:
    success: bool
    created_count: int = 0
    exceptions_count: int = 0
    raw_response: str = ""
    error_message: str = ""


@dataclass
class LedgerLine:
    """One side of a voucher entry (a debit or a credit)."""
    ledger_name: str
    amount: float
    is_debit: bool  # True = debit (Dr), False = credit (Cr)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _post_to_tally(xml_string: str) -> requests.Response | None:
    """
    Sends raw XML to the local Tally server and returns the raw
    requests.Response object, or None if the connection itself failed
    (Tally not running, wrong port, etc).
    """
    try:
        return requests.post(
            TALLY_URL,
            data=xml_string.encode("utf-8"),
            headers={"Content-Type": "text/xml"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.ConnectionError:
        return None


def _escape_xml(value: str) -> str:
    """
    Escapes special XML characters in user-facing text (ledger names,
    narrations, party names) before inserting into our XML strings.

    This matters because invoice data and ledger names can legitimately
    contain '&' (e.g. "Rent & Maintenance"), which is invalid raw XML
    unless escaped to '&amp;'. Without this, pushing a voucher referencing
    such a ledger would silently send malformed XML.
    """
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


# ---------------------------------------------------------------------------
# Public: reading ledgers
# ---------------------------------------------------------------------------

def get_ledger_names(company_name: str) -> LedgerFetchResult:
    """
    Fetches the full list of ledger names that exist in the given Tally
    company right now. This is the function every validation step in the
    app should call before allowing a push.
    """
    request_xml = f"""
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>List of Ledgers</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVCURRENTCOMPANY>{_escape_xml(company_name)}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>
"""

    response = _post_to_tally(request_xml)
    if response is None:
        return LedgerFetchResult(
            success=False,
            error_message=(
                "Could not connect to Tally. Make sure TallyPrime is open, "
                f"the company '{company_name}' is loaded, and the server is "
                "enabled on localhost:9000."
            ),
        )

    if response.status_code != 200:
        return LedgerFetchResult(
            success=False,
            error_message=f"Tally returned an unexpected HTTP status: {response.status_code}",
        )

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as e:
        return LedgerFetchResult(
            success=False,
            error_message=f"Could not parse Tally's response: {e}",
        )

    # A LINEERROR at this level (e.g. wrong company name) means we got
    # an error response shaped differently from the normal data response.
    line_error = root.find("LINEERROR")
    if line_error is not None:
        return LedgerFetchResult(
            success=False,
            error_message=f"Tally error: {line_error.text}",
        )

    ledger_names = [
        ledger_element.get("NAME")
        for ledger_element in root.iter("LEDGER")
        if ledger_element.get("NAME")
    ]

    return LedgerFetchResult(success=True, ledger_names=ledger_names)


# ---------------------------------------------------------------------------
# Public: validating ledgers before push
# ---------------------------------------------------------------------------

def find_missing_ledgers(required_ledger_names: list[str], company_name: str) -> list[str]:
    """
    Given a list of ledger names a voucher is about to use, returns the
    subset that do NOT currently exist in Tally. An empty list means
    everything is safe to push.

    This is the app-level safeguard that runs BEFORE we ever attempt a
    push, so the user gets a clear, specific message ("these ledgers
    don't exist") rather than relying solely on Tally's own rejection.
    """
    fetch_result = get_ledger_names(company_name)
    if not fetch_result.success:
        # If we can't even read the ledger list, we can't responsibly
        # claim anything is "safe" — treat every required ledger as
        # unverified/missing so the caller blocks the push and shows
        # the connection error instead.
        return required_ledger_names

    existing = set(fetch_result.ledger_names)
    return [name for name in required_ledger_names if name not in existing]


# ---------------------------------------------------------------------------
# Public: pushing a voucher
# ---------------------------------------------------------------------------

def push_voucher(
    company_name: str,
    voucher_type: str,
    voucher_date_yyyymmdd: str,
    party_ledger_name: str,
    lines: list[LedgerLine],
    narration: str = "",
    skip_validation: bool = False,
) -> VoucherPushResult:
    """
    Pushes a voucher to Tally.

    By default this performs a pre-push validation (every ledger in `lines`
    plus the party ledger must already exist in Tally) and refuses to send
    anything if validation fails. This is the "no autocreation" guarantee
    enforced at the application level, in addition to Tally enforcing it
    independently on its own side.

    `lines` should already be balanced (debits == credits) — this function
    does not currently re-check arithmetic balance; that belongs in a
    voucher-building step before this is called.
    """
    if not skip_validation:
        ledger_names_to_check = list({party_ledger_name, *[l.ledger_name for l in lines]})
        missing = find_missing_ledgers(ledger_names_to_check, company_name)
        if missing:
            return VoucherPushResult(
                success=False,
                error_message=(
                    "Push blocked — these ledgers do not exist in Tally and "
                    f"will not be auto-created: {', '.join(missing)}"
                ),
            )

    ledger_entries_xml = ""
    for line in lines:
        # Tally's sign convention: ISDEEMEDPOSITIVE=Yes pairs with a
        # NEGATIVE amount for a debit; ISDEEMEDPOSITIVE=No pairs with a
        # POSITIVE amount for a credit. Confirmed against a real Tally
        # instance during development — this is correct, not a typo.
        signed_amount = -abs(line.amount) if line.is_debit else abs(line.amount)
        is_deemed_positive = "Yes" if line.is_debit else "No"
        ledger_entries_xml += f"""
            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>{_escape_xml(line.ledger_name)}</LEDGERNAME>
              <ISDEEMEDPOSITIVE>{is_deemed_positive}</ISDEEMEDPOSITIVE>
              <AMOUNT>{signed_amount:.2f}</AMOUNT>
            </ALLLEDGERENTRIES.LIST>"""

    request_xml = f"""
<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>Vouchers</REPORTNAME>
        <STATICVARIABLES>
          <SVCURRENTCOMPANY>{_escape_xml(company_name)}</SVCURRENTCOMPANY>
        </STATICVARIABLES>
      </REQUESTDESC>
      <REQUESTDATA>
        <TALLYMESSAGE xmlns:UDF="TallyUDF">
          <VOUCHER VCHTYPE="{_escape_xml(voucher_type)}" ACTION="Create">
            <DATE>{voucher_date_yyyymmdd}</DATE>
            <VOUCHERTYPENAME>{_escape_xml(voucher_type)}</VOUCHERTYPENAME>
            <PARTYLEDGERNAME>{_escape_xml(party_ledger_name)}</PARTYLEDGERNAME>
            <NARRATION>{_escape_xml(narration)}</NARRATION>
{ledger_entries_xml}
          </VOUCHER>
        </TALLYMESSAGE>
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>
"""

    response = _post_to_tally(request_xml)
    if response is None:
        return VoucherPushResult(
            success=False,
            error_message="Could not connect to Tally during push. Nothing was sent.",
        )

    if response.status_code != 200:
        return VoucherPushResult(
            success=False,
            error_message=f"Tally returned an unexpected HTTP status: {response.status_code}",
            raw_response=response.text,
        )

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as e:
        return VoucherPushResult(
            success=False,
            error_message=f"Could not parse Tally's response: {e}",
            raw_response=response.text,
        )

    def _int_field(tag: str) -> int:
        element = root.find(tag)
        try:
            return int(element.text) if element is not None and element.text else 0
        except ValueError:
            return 0

    created = _int_field("CREATED")
    exceptions = _int_field("EXCEPTIONS")

    if created > 0 and exceptions == 0:
        return VoucherPushResult(
            success=True,
            created_count=created,
            exceptions_count=exceptions,
            raw_response=response.text,
        )

    # Something went wrong on Tally's side even though we validated
    # beforehand (e.g. a ledger was deleted in Tally between our check
    # and the push). Surface whatever explanation Tally gives, falling
    # back to a generic message if LINEERROR isn't present.
    line_error = root.find("LINEERROR")
    error_text = line_error.text if line_error is not None else "Tally rejected the voucher (no specific reason given)."

    return VoucherPushResult(
        success=False,
        created_count=created,
        exceptions_count=exceptions,
        raw_response=response.text,
        error_message=error_text,
    )