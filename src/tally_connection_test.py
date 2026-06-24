"""
Step 2 test script: confirms we can talk to a locally running TallyPrime
over its HTTP/XML server and fetch the list of ledgers for a given company.

This is a throwaway diagnostic script, not part of the final app structure.
"""

import requests
import xml.etree.ElementTree as ET

TALLY_URL = "http://localhost:9000"

# IMPORTANT: replace this with the exact company name as it appears in Tally
COMPANY_NAME = "Test1"

LEDGER_LIST_REQUEST_XML = f"""
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
        <SVCURRENTCOMPANY>{COMPANY_NAME}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>
"""


def fetch_ledger_names() -> list[str]:
    """
    Connects to local Tally, fetches the ledger list, and returns
    a plain list of ledger name strings. Returns an empty list if
    anything goes wrong (connection failure, unexpected response, etc).
    """
    try:
        response = requests.post(
            TALLY_URL,
            data=LEDGER_LIST_REQUEST_XML.encode("utf-8"),
            headers={"Content-Type": "text/xml"},
            timeout=10,
        )
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Tally at", TALLY_URL)
        print("   Check that TallyPrime is running, set as Server, on port 9000.")
        return []

    if response.status_code != 200:
        print(f"❌ Unexpected HTTP status: {response.status_code}")
        return []

    # Tally sometimes returns content that isn't strictly valid XML
    # (stray characters, encoding quirks). We guard parsing in a try block
    # so a malformed response doesn't crash the whole app later.
    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as e:
        print("❌ Could not parse Tally's response as XML:", e)
        return []

    ledger_names = []
    # Every <LEDGER NAME="..."> element anywhere in the response is a ledger.
    for ledger_element in root.iter("LEDGER"):
        name = ledger_element.get("NAME")
        if name:
            ledger_names.append(name)

    return ledger_names


if __name__ == "__main__":
    ledgers = fetch_ledger_names()
    if ledgers:
        print(f"✅ Found {len(ledgers)} ledger(s):\n")
        for name in ledgers:
            print(" -", name)
    else:
        print("No ledgers found, or an error occurred above.")