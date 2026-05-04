"""Phase 2 sync script for job-tracker.

Run by the scheduled-tasks routine every 30 min. Does NOT call any MCPs itself —
the routine prompt does the MCP calls (Drive, Gmail) and writes JSON files into
sync/state/ for this script to consume.

Lifecycle per run:
  1. routine: pulls latest applications.enc.json from GitHub
  2. this script: decrypts -> rows.json (sync/state/rows.json)
  3. routine: for each row's Company, queries Gmail MCP, writes hits to
     sync/state/gmail_hits.json
  4. this script: classifies each row's status from Gmail hits, updates rows
  5. this script: re-encrypts rows -> applications.enc.json
  6. routine: commits + pushes via PAT

CLI subcommands:
  decrypt   — read data/applications.enc.json, write sync/state/rows.json
  classify  — read sync/state/rows.json + sync/state/gmail_hits.json,
              update rows.json with new statuses, write sync/state/log.json
  encrypt   — read sync/state/rows.json, write data/applications.enc.json

Env required for decrypt/encrypt: JOBTRACKER_PASSWORD
"""
from __future__ import annotations

import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

REPO = Path(__file__).resolve().parent.parent
ENC_FILE = REPO / "data" / "applications.enc.json"
STATE = REPO / "sync" / "state"
ROWS_FILE = STATE / "rows.json"
HITS_FILE = STATE / "gmail_hits.json"
LOG_FILE = STATE / "log.json"

PBKDF2_ITERS = 200_000

STATUS_RANK = {
    "applied": 1, "screen": 2, "screening": 2,
    "oa": 3, "assessment": 3, "online assessment": 3,
    "interview": 4, "interviewing": 4, "phone screen": 4, "onsite": 5,
    "offer": 6, "accepted": 7,
    "rejected": -1, "declined": -1, "ghosted": -1,
}


def _password() -> bytes:
    pw = os.environ.get("JOBTRACKER_PASSWORD")
    if not pw:
        sys.exit("JOBTRACKER_PASSWORD env var not set")
    return pw.encode()


def _derive_key(password: bytes, salt: bytes) -> bytes:
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITERS
    ).derive(password)


def cmd_decrypt() -> None:
    if not ENC_FILE.exists():
        sys.exit(f"missing {ENC_FILE}")
    bundle = json.loads(ENC_FILE.read_text("utf-8"))
    salt = base64.b64decode(bundle["kdf"]["salt_b64"])
    iv = base64.b64decode(bundle["iv_b64"])
    ct = base64.b64decode(bundle["ct_b64"])
    key = _derive_key(_password(), salt)
    plaintext = AESGCM(key).decrypt(iv, ct, None)
    payload = json.loads(plaintext.decode("utf-8"))
    STATE.mkdir(parents=True, exist_ok=True)
    ROWS_FILE.write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"decrypted {len(payload.get('rows', []))} rows -> {ROWS_FILE}")


def cmd_encrypt() -> None:
    if not ROWS_FILE.exists():
        sys.exit(f"missing {ROWS_FILE}")
    payload = json.loads(ROWS_FILE.read_text("utf-8"))
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    plaintext = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = _derive_key(_password(), salt)
    ct = AESGCM(key).encrypt(iv, plaintext, None)
    bundle = {
        "v": 1,
        "kdf": {
            "name": "PBKDF2",
            "hash": "SHA-256",
            "iters": PBKDF2_ITERS,
            "salt_b64": base64.b64encode(salt).decode(),
        },
        "iv_b64": base64.b64encode(iv).decode(),
        "ct_b64": base64.b64encode(ct).decode(),
    }
    ENC_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENC_FILE.write_text(json.dumps(bundle, indent=2), "utf-8")
    print(f"encrypted {len(payload.get('rows', []))} rows -> {ENC_FILE}")


def _classify(subject: str, snippet: str, current_status: str) -> tuple[str | None, str]:
    text = (subject + " " + snippet).lower()

    rules = [
        (("offer", "pleased to extend", "we'd like to extend"), "Offer"),
        (("unfortunately", "regret", "not moving forward",
          "decided to move forward with other", "decided to proceed with other",
          "no longer being considered"), "Rejected"),
        (("online assessment", "coding challenge", "hackerrank", "codility",
          "codesignal", "take-home", "takehome"), "OA"),
        (("phone screen", "schedule a call", "next step", "next steps",
          "interview invitation", "would like to interview", "onsite",
          "on-site", "technical interview"), "Interview"),
        (("received your application", "thank you for applying",
          "we received your application"), "Applied"),
    ]

    for keywords, label in rules:
        if any(k in text for k in keywords):
            cur_rank = STATUS_RANK.get((current_status or "").lower(), 0)
            new_rank = STATUS_RANK.get(label.lower(), 0)
            # Allow Rejected to override anything; otherwise only advance.
            if label == "Rejected" or new_rank > cur_rank:
                return label, label
            return None, label
    return None, ""


def cmd_classify() -> None:
    if not ROWS_FILE.exists():
        sys.exit(f"missing {ROWS_FILE}")
    if not HITS_FILE.exists():
        sys.exit(f"missing {HITS_FILE} (routine should write this before classify)")

    payload = json.loads(ROWS_FILE.read_text("utf-8"))
    hits = json.loads(HITS_FILE.read_text("utf-8"))  # {company: [{subject, snippet, date}]}
    rows = payload.get("rows", [])

    # Detect column names dynamically.
    if not rows:
        print("no rows to classify")
        return
    cols = list(rows[0].keys())
    company_key = next((c for c in cols if c.lower() == "company"), None)
    status_key = next((c for c in cols if c.lower() == "status"), None)
    last_update_key = next((c for c in cols if "last" in c.lower() and "update" in c.lower()), None)

    if not company_key:
        sys.exit("no Company column found; cannot classify")
    if not status_key:
        # Add it
        status_key = "Status"
        for r in rows:
            r.setdefault(status_key, "")

    log_entries = []
    for r in rows:
        company = (r.get(company_key) or "").strip()
        if not company:
            continue
        company_hits = hits.get(company, [])
        if not company_hits:
            continue
        # Use the most recent hit
        latest = sorted(company_hits, key=lambda h: h.get("date", ""), reverse=True)[0]
        new_status, considered = _classify(
            latest.get("subject", ""), latest.get("snippet", ""), r.get(status_key, "")
        )
        if new_status and new_status != r.get(status_key):
            log_entries.append({
                "company": company,
                "old_status": r.get(status_key, ""),
                "new_status": new_status,
                "subject": latest.get("subject", ""),
                "date": latest.get("date", ""),
            })
            r[status_key] = new_status
            if last_update_key:
                r[last_update_key] = latest.get("date", "")[:10]

    payload["rows"] = rows
    ROWS_FILE.write_text(json.dumps(payload, indent=2), "utf-8")

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps({
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "changed": log_entries,
    }, indent=2), "utf-8")
    print(f"classified {len(rows)} rows; {len(log_entries)} changes -> {LOG_FILE}")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"decrypt", "encrypt", "classify"}:
        sys.exit("usage: sync.py {decrypt|encrypt|classify}")
    {"decrypt": cmd_decrypt, "encrypt": cmd_encrypt, "classify": cmd_classify}[sys.argv[1]]()


if __name__ == "__main__":
    main()
