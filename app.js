// Job Tracker — client-side decryption + search.
// Data file format (data/applications.enc.json):
// {
//   "v": 1,
//   "kdf": { "name": "PBKDF2", "hash": "SHA-256", "iters": 200000, "salt_b64": "..." },
//   "iv_b64": "...",
//   "ct_b64": "..."   // AES-GCM ciphertext with appended 16-byte tag (WebCrypto default)
// }

const DATA_URL = "data/applications.enc.json";

function b64ToBytes(b64) {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function deriveKey(password, saltBytes, iters, hash) {
  const baseKey = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    { name: "PBKDF2" },
    false,
    ["deriveKey"]
  );
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt: saltBytes, iterations: iters, hash },
    baseKey,
    { name: "AES-GCM", length: 256 },
    false,
    ["decrypt"]
  );
}

async function decryptBundle(bundle, password) {
  const salt = b64ToBytes(bundle.kdf.salt_b64);
  const iv = b64ToBytes(bundle.iv_b64);
  const ct = b64ToBytes(bundle.ct_b64);
  const key = await deriveKey(password, salt, bundle.kdf.iters, bundle.kdf.hash);
  const plaintext = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, ct);
  return JSON.parse(new TextDecoder().decode(plaintext));
}

let allRows = [];
let columns = [];

function detectStatusKey(cols) {
  return cols.find(c => /^status$/i.test(c)) || null;
}

function detectLinkKey(cols) {
  return cols.find(c => /(link|url|posting)/i.test(c)) || null;
}

function statusClass(value) {
  if (!value) return "";
  return String(value).toLowerCase().replace(/[^a-z]/g, "");
}

function renderHead(cols) {
  const tr = document.getElementById("grid-head");
  tr.innerHTML = "";
  for (const c of cols) {
    const th = document.createElement("th");
    th.textContent = c;
    tr.appendChild(th);
  }
}

function cellRender(col, value, statusKey, linkKey) {
  const td = document.createElement("td");
  if (value == null || value === "") return td;
  const text = String(value);
  if (col === statusKey) {
    const span = document.createElement("span");
    span.className = "status-pill " + statusClass(text);
    span.textContent = text;
    td.appendChild(span);
    return td;
  }
  if (col === linkKey && /^https?:\/\//i.test(text)) {
    const a = document.createElement("a");
    a.href = text;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = "open";
    td.appendChild(a);
    return td;
  }
  td.textContent = text;
  return td;
}

function renderRows(rows) {
  const body = document.getElementById("grid-body");
  body.innerHTML = "";
  const statusKey = detectStatusKey(columns);
  const linkKey = detectLinkKey(columns);
  const frag = document.createDocumentFragment();
  for (const r of rows) {
    const tr = document.createElement("tr");
    for (const c of columns) {
      tr.appendChild(cellRender(c, r[c], statusKey, linkKey));
    }
    frag.appendChild(tr);
  }
  body.appendChild(frag);
  document.getElementById("count").textContent =
    rows.length + " of " + allRows.length;
  document.getElementById("empty").hidden = rows.length > 0;
}

function filterRows(query) {
  const q = query.trim().toLowerCase();
  if (!q) return allRows;
  return allRows.filter(r => {
    for (const c of columns) {
      const v = r[c];
      if (v != null && String(v).toLowerCase().includes(q)) return true;
    }
    return false;
  });
}

function setupSearch() {
  const input = document.getElementById("search");
  input.addEventListener("input", () => renderRows(filterRows(input.value)));
}

function showApp(payload) {
  document.getElementById("gate").hidden = true;
  document.getElementById("app").hidden = false;

  allRows = Array.isArray(payload.rows) ? payload.rows : [];
  // Column order: union of keys, preserving first-row order then any new keys.
  const seen = new Set();
  columns = [];
  if (allRows.length) {
    for (const k of Object.keys(allRows[0])) { columns.push(k); seen.add(k); }
    for (const r of allRows) {
      for (const k of Object.keys(r)) {
        if (!seen.has(k)) { columns.push(k); seen.add(k); }
      }
    }
  }

  if (payload.updated_at) {
    document.getElementById("meta").textContent =
      "Updated " + new Date(payload.updated_at).toLocaleString();
  }

  renderHead(columns);
  renderRows(allRows);
  setupSearch();
  document.getElementById("search").focus();
}

async function tryUnlock(password) {
  const errorEl = document.getElementById("gate-error");
  errorEl.hidden = true;
  let bundle;
  try {
    const res = await fetch(DATA_URL, { cache: "no-store" });
    if (!res.ok) throw new Error("data file not found");
    bundle = await res.json();
  } catch (e) {
    errorEl.textContent = "Could not load data file. Has admin.html been used to create one yet?";
    errorEl.hidden = false;
    return;
  }
  try {
    const payload = await decryptBundle(bundle, password);
    sessionStorage.setItem("jt-pw", password); // keep for this tab session only
    showApp(payload);
  } catch (e) {
    errorEl.textContent = "Wrong password.";
    errorEl.hidden = false;
  }
}

document.getElementById("unlock-form").addEventListener("submit", (e) => {
  e.preventDefault();
  tryUnlock(document.getElementById("password").value);
});

// Auto-unlock if we have a session password (refresh-friendly).
const cached = sessionStorage.getItem("jt-pw");
if (cached) tryUnlock(cached);
