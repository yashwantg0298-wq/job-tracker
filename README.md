# Job Tracker

A static, password-protected site for searching your job applications. The data file is AES-GCM encrypted client-side, so even though the site is hosted publicly on GitHub Pages, the contents are unreadable without the password.

## What's here

- `index.html` / `app.js` / `styles.css` — the tracker UI: glassmorphism login + Kanban dashboard with company logos + per-application detail view (hash-routed at `#/app/<id>`).
- `admin.html` — one-page tool that runs entirely in your browser to edit applications and re-encrypt the data file.
- `data/applications.enc.json` — encrypted data bundle. Created/replaced via `admin.html`.
- `sync/` — design and instructions for the Phase 2 scheduled sync agent.

## Your password

Your password is **not stored in this repo**. It lives only in `sync/.secrets.env` (gitignored) on your machine and in your password manager.

If you lose it:
1. You lose the ability to read existing encrypted data.
2. You'll need to regenerate a new password and rebuild the data file from your source-of-truth Google Sheet using `admin.html`.

The password is used both to unlock the tracker and to encrypt new data via `admin.html`.

## First-time setup

### 1. Create the GitHub repo

You don't have `gh` installed, so use the web UI:

1. Go to https://github.com/new
2. Name: **job-tracker**
3. Visibility: **Public** (required for free GitHub Pages — the data file is encrypted, so this is safe)
4. Don't add README, .gitignore, or license (this folder already has them)
5. Create repository

### 2. Push this folder

```bash
git init
git add .
git commit -m "Initial job tracker scaffold"
git branch -M main
git remote add origin https://github.com/<your-username>/job-tracker.git
git push -u origin main
```

### 3. Enable GitHub Pages

1. In the repo on github.com → **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: **main** / **/ (root)** → Save
4. Wait ~1 minute. URL will be `https://<your-username>.github.io/job-tracker/`

### 4. Generate / update encrypted data

1. Open `https://<your-username>.github.io/job-tracker/admin.html` (or open `admin.html` locally in a browser)
2. Enter your password to unlock and load the existing data
3. Edit applications, add new ones, fill in STAR stories
4. Click **Encrypt and download** → it downloads `applications.enc.json`
5. Move/replace that file into `data/applications.enc.json`
6. `git add data/applications.enc.json && git commit -m "Update data" && git push`

### 5. Visit the site

Open `https://<your-username>.github.io/job-tracker/`, enter the password, browse the Kanban board, click any card for the detail view.

## Per-application fields

Every row supports these keys:

| Field | Notes |
| --- | --- |
| Company | Display name |
| Domain | e.g. `tesla.com` — used to fetch the company logo via `logo.clearbit.com` (with Google favicon fallback). |
| Role / Position | |
| Status | Free text. Mapped to a Kanban column heuristically (Wishlist / Applied / Interviewing / Offer / Rejected). |
| Date Applied | |
| Location, Platform, Tier, Grade, Job ID / Req | |
| Salary Band | Their range |
| Quote CTC | Your number |
| Fit % | 0-100 — drives the gauge on the detail page |
| Chances | Free text e.g. "Moderate (25-40%)" |
| Role Summary (JD) | Job description — shown on the detail page |
| STAR Story | Your STAR for this role — shown on the detail page |
| Next Step | What to do next |
| Notes / Key Facts | Free-form notes |

## Schema-flexible

If you add a new key in `admin.html`, it'll be saved into the encrypted file. The detail page renders only the keys it knows; extras are preserved but hidden. Future versions can surface them.

## Phase 2: scheduled Gmail sync

Phase 2 will be a scheduled remote agent that every ~30 minutes:

1. Reads your Drive xlsx
2. Searches your Gmail for each company in the Applications tab
3. Updates statuses based on what it finds (interview invites, rejections, etc.)
4. Writes the xlsx back to Drive
5. Re-encrypts JSON with your password and pushes to this repo

See [`sync/AGENT_INSTRUCTIONS.md`](sync/AGENT_INSTRUCTIONS.md) for the full design and the steps to enable it.
