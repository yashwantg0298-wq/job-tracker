# Job Tracker

A static, password-protected site for searching your job applications. The data file is AES-GCM encrypted client-side, so even though the site is hosted publicly on GitHub Pages, the contents are unreadable without the password.

## What's here

- `index.html` / `app.js` / `styles.css` — the tracker UI (search by company, role, status, anything).
- `admin.html` — one-page tool that runs entirely in your browser to encrypt a JSON payload into the format the tracker reads.
- `data/applications.enc.json` — encrypted data bundle. Created via `admin.html`.
- `sync/` — design and instructions for the Phase 2 scheduled sync agent.

## Your password

```
sz1R3RfRPlFC7jdsSTN8
```

This was generated for you. Save it somewhere safe (a password manager). It's used both to unlock the tracker and to encrypt new data via `admin.html`. **It is not stored anywhere in this repo** — if you lose it, you lose access to existing encrypted data and have to regenerate.

## First-time setup

### 1. Create the GitHub repo

You don't have `gh` installed, so use the web UI:

1. Go to https://github.com/new
2. Name: **job-tracker**
3. Visibility: **Public** (required for free GitHub Pages)
4. Don't add README, .gitignore, or license (this folder already has them)
5. Create repository

### 2. Push this folder

From `D:\Job\job-tracker`:

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

### 4. Generate your first encrypted data file

1. Open `https://<your-username>.github.io/job-tracker/admin.html` (or open `admin.html` locally in a browser)
2. Click **Load sample** to see the JSON shape — replace it with your own row data
3. Paste your password
4. Click **Encrypt and download** → it downloads `applications.enc.json`
5. Move/replace that file into `data/applications.enc.json`
6. `git add data/applications.enc.json && git commit -m "Update data" && git push`

### 5. Visit the site

Open `https://<your-username>.github.io/job-tracker/`, enter the password, search.

## Updating data manually

Use `admin.html`. The browser does the encryption — your password and raw data never leave your machine.

## Schema

The tracker is schema-flexible. Whatever keys exist in the first row of your `rows` array become columns, in order. Special handling:

- A column named **Status** (case-insensitive) renders as a colored pill. Recognized words (mapped to colors): applied, interview, interviewing, oa, assessment, offer, accepted, rejected, declined, ghosted.
- A column whose name contains **Link** / **URL** / **Posting** renders as a clickable "open" link if the value starts with http(s).

Any other column name renders as plain text.

## Phase 2: scheduled Gmail sync

Phase 2 (not yet wired up) will be a scheduled remote agent that every ~30 minutes:

1. Reads your Drive xlsx
2. Searches your Gmail for each company in the Applications tab
3. Updates statuses based on what it finds (interview invites, rejections, etc.)
4. Writes the xlsx back to Drive
5. Re-encrypts JSON with your password and pushes to this repo

See [`sync/AGENT_INSTRUCTIONS.md`](sync/AGENT_INSTRUCTIONS.md) for the full design and the steps to enable it.
