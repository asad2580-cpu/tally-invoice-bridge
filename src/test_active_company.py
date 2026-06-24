"""
Tests whether Tally tells us which company is currently active, either
by omitting SVCURRENTCOMPANY (to see if Tally defaults to the active
one) or via a "List of Companies" collection request.
"""

import requests

TALLY_URL = "http://localhost:9000"

# Attempt 1: List of Companies collection, no company specified.
request_xml_1 = """
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>List of Companies</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVISSIMPLECOMPANY>No</SVISSIMPLECOMPANY>
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>
"""

print("=== Attempt 1: List of Companies ===")
response = requests.post(TALLY_URL, data=request_xml_1.encode("utf-8"), headers={"Content-Type": "text/xml"}, timeout=10)
print("Status:", response.status_code)
print(response.text)
print()

# Attempt 2: Ledger list request with NO SVCURRENTCOMPANY at all,
# to see if Tally defaults to the currently active company.
request_xml_2 = """
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
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>
"""

print("=== Attempt 2: Ledgers, no company specified (testing default behavior) ===")
response2 = requests.post(TALLY_URL, data=request_xml_2.encode("utf-8"), headers={"Content-Type": "text/xml"}, timeout=10)
print("Status:", response2.status_code)
print(response2.text[:1000])  # first 1000 chars, just to see if it worked and what company it used