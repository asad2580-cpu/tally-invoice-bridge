
"""
Step 3 test script: builds a Purchase voucher XML, prints it for review,
then sends it to local Tally and prints Tally's raw response.

This is a throwaway diagnostic script, not part of the final app structure.
"""

import requests
import xml.etree.ElementTree as ET

TALLY_URL = "http://localhost:9000"

# IMPORTANT: replace with the exact company name as it appears in Tally
COMPANY_NAME = "Test1"

# IMPORTANT: these must be EXACT, EXISTING ledger names in your Tally company.
# We are deliberately NOT creating them — only referencing them.
PARTY_LEDGER = "non-existent ledger"        # credited (we owe them money)
PURCHASE_LEDGER = "Purchase Account"   # debited (replace if your ledger is named differently)

VOUCHER_DATE = "20260601"  # YYYYMMDD format, must be an education-mode-allowed date
AMOUNT = "5000.00"


def build_purchase_voucher_xml() -> str:
    return f"""
<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>Vouchers</REPORTNAME>
        <STATICVARIABLES>
          <SVCURRENTCOMPANY>{COMPANY_NAME}</SVCURRENTCOMPANY>
        </STATICVARIABLES>
      </REQUESTDESC>
      <REQUESTDATA>
        <TALLYMESSAGE xmlns:UDF="TallyUDF">
          <VOUCHER VCHTYPE="Purchase" ACTION="Create">
            <DATE>{VOUCHER_DATE}</DATE>
            <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
            <PARTYLEDGERNAME>{PARTY_LEDGER}</PARTYLEDGERNAME>
            <NARRATION>Test purchase voucher from Tally Invoice Bridge</NARRATION>

            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>{PURCHASE_LEDGER}</LEDGERNAME>
              <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
              <AMOUNT>-{AMOUNT}</AMOUNT>
            </ALLLEDGERENTRIES.LIST>

            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>{PARTY_LEDGER}</LEDGERNAME>
              <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
              <AMOUNT>{AMOUNT}</AMOUNT>
            </ALLLEDGERENTRIES.LIST>

          </VOUCHER>
        </TALLYMESSAGE>
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>
"""


def push_voucher(xml_string: str):
    try:
        response = requests.post(
            TALLY_URL,
            data=xml_string.encode("utf-8"),
            headers={"Content-Type": "text/xml"},
            timeout=10,
        )
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Tally at", TALLY_URL)
        return

    print("Status code:", response.status_code)
    print("----- RAW RESPONSE START -----")
    print(response.text)
    print("----- RAW RESPONSE END -----")


if __name__ == "__main__":
    xml_to_send = build_purchase_voucher_xml()

    print("===== XML ABOUT TO BE SENT =====")
    print(xml_to_send)
    print("===== END XML =====\n")

    confirm = input("Send this to Tally now? (y/n): ").strip().lower()
    if confirm == "y":
        push_voucher(xml_to_send)
    else:
        print("Cancelled — nothing was sent.")