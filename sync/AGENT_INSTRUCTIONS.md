# Phase 2: Scheduled sync agent

## Goal

Every ~30 minutes, automatically:

1. Pull the latest Application rows from the Drive xlsx (file ID `1Qp6ml5YKs3hhhiocIM7OnLFIjWDNQZVn`)
2. For each row, check Gmail for new threads about that application
3. Update the row's status / last-update date if the email signals a change
4. Write the modified xlsx back to Drive
5. Re-encrypt rows as JSON using the site's password
6. Commit + push the new `data/applications.enc.json` to this repo so GitHub Pages serves fresh data

## What's needed before this can run

The agent runs as a **remote Claude routine** (via the `schedule` skill / `mcp__scheduled-tasks` MCP) — not a local cron job, because the Gmail and Drive MCPs are only callable from inside a Claude session.

### Secrets the routine needs

Stored in the routine's environment, NOT in this repo:

- `JOBTRACKER_PASSWORD` — the same password used to unlock the site (`sz1R3RfRPlFC7jdsSTN8`). Used to AES-encrypt the JSON the same way `admin.html` does.
- `GH_TOKEN` — a GitHub fine-grained Personal Access Token with **Contents: Read & Write** on the `job-tracker` repo only. Used to push commits without interactive auth.
  - Create at: https://github.com/settings/personal-access-tokens/new
  - Repository access: Only select repositories → `job-tracker`
  - Permissions: Contents → Read and write

### Repo permissions

GitHub Pages re-deploys automatically on push to `main`. Nothing extra to configure beyond the initial Pages setup in the README.

## How the agent works (step by step)

When the routine fires, it does this in sequence:

### Step 1 — Read the xlsx

Use `mcp__1d5f3a47-686b-4bf7-ad3b-1dc5a8632eff__download_file_content` with file ID `1Qp6ml5YKs3hhhiocIM7OnLFIjWDNQZVn`.

The MCP returns base64. Decode it. Use Python (`openpyxl`) inside the routine sandbox to parse:
- Sheet: `Applications`
- Row 1 = column headers
- Rows 2..N = applications

Build a list of dicts: `[{"Company": "...", "Role": "...", "Status": "...", ...}, ...]`

### Step 2 — Heuristic Gmail scan per row

For each row that has a Company name, call `mcp__d95fb8ca-9997-4a2a-af54-53b35c1e3a33__search_threads` with a query like:

```
from:(@<company>.com) OR subject:"<Company>" newer_than:60d
```

For each returned thread, fetch the full thread (`mcp__...get_thread`) and extract the most recent message subject + snippet.

### Step 3 — Classify

Apply simple keyword heuristics on the most recent message subject + body:

| If matches | Set Status to | Set Last Update to |
|---|---|---|
| "unfortunately", "regret", "not moving forward", "decided to move forward with other" | `Rejected` | message date |
| "interview", "schedule a call", "next step", "phone screen", "onsite" | `Interview` | message date |
| "online assessment", "OA", "coding challenge", "HackerRank", "Codility" | `OA` | message date |
| "offer", "pleased to extend", "we'd like to extend" | `Offer` | message date |
| "received your application", "thank you for applying" | leave unchanged (just confirms applied) | message date |

Only update if the new classification is **more advanced** than the existing one (don't overwrite Offer with Applied just because a confirmation email arrived).

### Step 4 — Write back to xlsx

Modify the openpyxl workbook in memory. Add a new sheet `Sync Log` (or append to it) with `[timestamp, company, old_status, new_status, message_subject]` for every change. Save to bytes.

Upload back to Drive: there's no MCP tool for uploading currently. **TODO:** This step needs either:
- A Drive MCP `upload_file` / `update_file` tool that doesn't exist yet, OR
- A Google Drive API call from the sandbox using a stored OAuth token, OR
- Skip writing back to Drive and treat the encrypted JSON in this repo as the source of truth, with the xlsx being a one-time bootstrap.

**Recommendation:** start with option 3 (don't write back to Drive). The website is the live view; the xlsx is just the seed. If you want to keep the xlsx in sync, do it manually for now.

### Step 5 — Encrypt as JSON

Use Python's `cryptography` library to mirror the WebCrypto format used by `admin.html`:

```python
import os, json, base64
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

password = os.environ["JOBTRACKER_PASSWORD"].encode()
salt = os.urandom(16)
iv = os.urandom(12)
key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=200_000).derive(password)
plaintext = json.dumps({"updated_at": "...", "rows": rows}).encode()
ct = AESGCM(key).encrypt(iv, plaintext, None)  # ct includes 16-byte tag at end

bundle = {
  "v": 1,
  "kdf": {"name": "PBKDF2", "hash": "SHA-256", "iters": 200_000, "salt_b64": base64.b64encode(salt).decode()},
  "iv_b64": base64.b64encode(iv).decode(),
  "ct_b64": base64.b64encode(ct).decode(),
}
```

The `ct_b64` field includes the 16-byte GCM tag appended (this matches WebCrypto's behavior, so `app.js` decrypts cleanly).

### Step 6 — Push to GitHub

```bash
git clone https://x-access-token:$GH_TOKEN@github.com/<user>/job-tracker.git
cd job-tracker
# overwrite data/applications.enc.json with the new bundle
git add data/applications.enc.json
git commit -m "Auto-sync $(date -u +%Y-%m-%dT%H:%MZ)"
git push
```

GitHub Pages will redeploy within a minute.

## How to enable this routine

When you're ready, ask Claude:

> "Set up the Phase 2 scheduled sync routine using the design in `D:\Job\job-tracker\sync\AGENT_INSTRUCTIONS.md`. The repo is at github.com/<your-user>/job-tracker. I'll provide the GitHub PAT."

Claude will use the `schedule` skill / `mcp__scheduled-tasks` MCP to create a recurring routine. You'll need to paste the PAT and confirm the password.

## Resolved decisions (2026-05-04)

1. **xlsx writeback:** disabled. The encrypted JSON in this repo is the source of truth. The Drive xlsx is treated as a one-time seed only. Step 4 above is skipped — no Drive upload happens.
2. **First-run behavior:** import-all. The first invocation reads every row from the Drive xlsx, encrypts it, and pushes it to overwrite whatever is currently in `data/applications.enc.json`. Subsequent runs only update statuses based on Gmail.
3. **Status vocabulary:** unconfirmed (couldn't read the xlsx in setup). The classifier in Step 3 will preserve whatever status string already exists on a row unless Gmail provides clear evidence to advance it. If your sheet uses non-standard status names, the routine logs them in `Sync Log` and leaves them alone.
