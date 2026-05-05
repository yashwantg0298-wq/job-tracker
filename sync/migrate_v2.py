"""One-shot migration: adds Domain + STAR Story fields to every row.

Run after `sync.py decrypt`, then run `sync.py encrypt` to write the new bundle.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ROWS_FILE = ROOT / "state" / "rows.json"

DOMAINS = {
    "Accenture": "accenture.com",
    "Acuity Knowledge Partners": "acuitykp.com",
    "Amazon India": "amazon.in",
    "Apexon": "apexon.com",
    "Barclays": "barclays.com",
    "CRISIL (S&P Global)": "crisil.com",
    "Capgemini": "capgemini.com",
    "Citi": "citi.com",
    "Deloitte USI": "deloitte.com",
    "E2M Solutions": "e2msolutions.com",
    "EXL Service": "exlservice.com",
    "EY India": "ey.com",
    "Evalueserve": "evalueserve.com",
    "Exxat Group": "exxat.com",
    "Genpact": "genpact.com",
    "Grant Thornton Bharat": "grantthornton.in",
    "Hilti India": "hilti.com",
    "JPMorgan Chase": "jpmorganchase.com",
    "KPMG India / KGS": "kpmg.com",
    "Kraft Heinz India": "kraftheinzcompany.com",
    "NielsenIQ": "nielseniq.com",
    "PwC India": "pwc.com",
    "WNS Global Services": "wns.com",
    "Zetwerk": "zetwerk.com",
}


def guess_domain(company: str) -> str:
    if not company:
        return ""
    if company in DOMAINS:
        return DOMAINS[company]
    if company.startswith("[") and company.endswith("]"):
        return ""
    slug = re.sub(r"[^a-z0-9]", "", company.lower())
    if slug:
        return f"{slug}.com"
    return ""


def main() -> None:
    payload = json.loads(ROWS_FILE.read_text("utf-8"))
    rows = payload.get("rows", [])
    added_domain = 0
    added_star = 0
    for r in rows:
        if "Domain" not in r:
            r["Domain"] = guess_domain(r.get("Company", ""))
            added_domain += 1
        if "STAR Story" not in r:
            r["STAR Story"] = ""
            added_star += 1
    ROWS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), "utf-8"
    )
    print(f"added Domain to {added_domain} rows, STAR Story to {added_star} rows")
    blanks = [r["Company"] for r in rows if not r.get("Domain")]
    if blanks:
        print(f"no domain set for: {blanks}")


if __name__ == "__main__":
    main()
