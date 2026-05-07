// Job Tracker — client-side decryption, Kanban board, hash-routed detail view.

const DATA_URL = "data/applications.enc.json";

// ---- crypto ----
function b64ToBytes(b64) {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}
async function deriveKey(password, saltBytes, iters, hash) {
  const baseKey = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(password),
    { name: "PBKDF2" }, false, ["deriveKey"]
  );
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt: saltBytes, iterations: iters, hash },
    baseKey, { name: "AES-GCM", length: 256 }, false, ["decrypt"]
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

// ---- state ----
const state = { rows: [], updatedAt: null, query: "", showRejected: false };

// ---- columns / status mapping ----
const COLUMNS = [
  { key: "wishlist",  label: "Wishlist" },
  { key: "applied",   label: "Applied" },
  { key: "interview", label: "Interviewing" },
  { key: "offer",     label: "Offer" },
];
const REJECTED = { key: "rejected", label: "Rejected" };

function statusToColumn(status) {
  const s = (status || "").toLowerCase();
  if (!s) return "wishlist";
  if (/(reject|declined|ghost)/.test(s)) return "rejected";
  if (/offer|accepted/.test(s)) return "offer";
  if (/(interview|onsite|phone screen|tech screen|recruiter|under review|under consideration|active|test|assessment|oa)/.test(s)) return "interview";
  if (/(applied|application|submitted|received|sent|questionnaire|additional info)/.test(s)) return "applied";
  return "wishlist";
}

function statusPillClass(status) {
  return statusToColumn(status); // pill class names match column keys
}

// ---- logo lookup ----
function slugify(s) {
  return String(s || "").toLowerCase().trim()
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}
function logoCandidates(row) {
  const domain = (row.Domain || "").trim();
  const company = (row.Company || "").trim();
  const out = [];
  // 1) Per-row override (user-supplied URL)
  if (row.LogoUrl) out.push(row.LogoUrl);
  // 2) Local logo bundled in repo
  if (company) out.push(`data/logos/${slugify(company)}.png`);
  if (!domain) return out;
  // 3) Network sources (chained, all CORS-safe for <img> tags)
  out.push(`https://logo.uplead.com/${domain}`);
  out.push(`https://www.google.com/s2/favicons?domain=${domain}&sz=256`);
  out.push(`https://icons.duckduckgo.com/ip3/${domain}.ico`);
  return out;
}

function makeLogo(row) {
  const wrap = document.createElement("div");
  wrap.className = "logo";
  const initial = (row.Company || "?").trim().charAt(0).toUpperCase();
  const candidates = logoCandidates(row);

  const showMonogram = () => {
    wrap.replaceChildren();
    const m = document.createElement("span");
    m.className = "monogram";
    m.textContent = initial;
    wrap.appendChild(m);
  };

  if (!candidates.length) { showMonogram(); return wrap; }

  // Start with an empty white-plate placeholder; swap to monogram only if all
  // candidates fail. Never show monogram and image at the same time.
  const img = document.createElement("img");
  img.alt = "";
  let idx = 0;
  const tryNext = () => {
    idx += 1;
    if (idx < candidates.length) img.src = candidates[idx];
    else showMonogram();
  };
  img.onerror = tryNext;
  img.onload = () => {
    // Reject placeholder/globe icons that some services return for unknown domains.
    if (img.naturalWidth < 24 || img.naturalHeight < 24) tryNext();
  };
  img.src = candidates[0];
  wrap.appendChild(img);
  return wrap;
}

// ---- helpers ----
function ce(tag, props = {}, children = []) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") el.className = v;
    else if (k === "html") el.innerHTML = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (v != null) el.setAttribute(k, v);
  }
  for (const c of children) {
    if (c == null) continue;
    el.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return el;
}

function rowId(row, idx) {
  // stable-ish per row: prefer Job ID, else Company-DateApplied-idx
  const jid = (row["Job ID / Req"] || "").toString().trim();
  if (jid) return "j-" + jid.replace(/[^a-z0-9]/gi, "-").toLowerCase();
  const c = (row.Company || "").toString().trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");
  const d = (row["Date Applied"] || "").toString().trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return `r-${c}-${d}-${idx}`;
}

function parsePct(s) {
  if (s == null) return null;
  const m = String(s).match(/(\d{1,3})/);
  if (!m) return null;
  const n = parseInt(m[1], 10);
  return Number.isFinite(n) && n >= 0 && n <= 100 ? n : null;
}

function rowMatchesQuery(row, q) {
  if (!q) return true;
  q = q.trim().toLowerCase();
  if (!q) return true;
  for (const v of Object.values(row)) {
    if (v != null && String(v).toLowerCase().includes(q)) return true;
  }
  return false;
}

// ---- views ----
function renderDashboard() {
  const root = document.getElementById("view-root");
  root.innerHTML = "";

  const head = ce("div", { class: "main-head" }, [
    ce("h1", { text: "Job Tracker Dashboard" }),
    ce("div", { class: "head-actions" }, [
      ce("input", {
        class: "search", type: "search", placeholder: "Search company, role, status...",
        value: state.query, oninput: (e) => { state.query = e.target.value; renderKanban(); }
      }),
      ce("button", {
        class: "btn-primary",
        onclick: () => { window.location.href = "admin.html"; }
      }, ["+ Add New Application"]),
    ])
  ]);
  root.appendChild(head);

  const board = ce("div", { id: "kanban", class: "kanban" });
  root.appendChild(board);

  const rejectedRows = state.rows.filter(r => statusToColumn(r.Status) === "rejected");
  if (rejectedRows.length) {
    const toggle = ce("button", {
      class: "toggle-rejected",
      style: "margin-top: 18px;",
      onclick: () => { state.showRejected = !state.showRejected; renderKanban(); }
    });
    toggle.id = "toggle-rejected";
    root.appendChild(toggle);
  }

  renderKanban();
  renderUpcoming();
}

function renderKanban() {
  const board = document.getElementById("kanban");
  if (!board) return;
  board.innerHTML = "";
  board.classList.toggle("with-rejected", state.showRejected);

  const cols = state.showRejected ? [...COLUMNS, REJECTED] : COLUMNS;
  const buckets = Object.fromEntries(cols.map(c => [c.key, []]));
  state.rows.forEach((row, idx) => {
    if (!rowMatchesQuery(row, state.query)) return;
    const col = statusToColumn(row.Status);
    if (!buckets[col]) return;
    buckets[col].push({ row, idx });
  });

  for (const c of cols) {
    const col = ce("div", { class: `column ${c.key}` });
    col.appendChild(ce("div", { class: "col-head" }, [
      ce("span", { class: "title", text: c.label }),
      ce("span", { class: "count", text: `(${buckets[c.key].length})` }),
    ]));
    const list = ce("div", { class: "col-list" });
    if (!buckets[c.key].length) {
      list.appendChild(ce("div", { class: "empty-col", text: "—" }));
    } else {
      for (const { row, idx } of buckets[c.key]) list.appendChild(renderCard(row, idx));
    }
    col.appendChild(list);
    board.appendChild(col);
  }

  const t = document.getElementById("toggle-rejected");
  if (t) {
    const n = state.rows.filter(r => statusToColumn(r.Status) === "rejected").length;
    t.textContent = state.showRejected ? `Hide rejected (${n})` : `Show rejected (${n})`;
  }
}

function renderCard(row, idx) {
  const id = rowId(row, idx);
  const card = ce("a", { class: "card", href: `#/app/${id}` });

  const dots = ce("div", { class: "drag-dots", "aria-hidden": "true" });
  for (let i = 0; i < 6; i++) dots.appendChild(ce("span"));
  card.appendChild(dots);

  const head = ce("div", { class: "card-head" }, [
    makeLogo(row),
    ce("div", {}, [
      ce("div", { class: "card-company", text: row.Company || "—" }),
      ce("div", { class: "card-role", text: row["Role / Position"] || "" }),
    ]),
  ]);
  card.appendChild(head);

  if (row["Quote CTC"] || row["Salary Band"]) {
    card.appendChild(ce("div", { class: "kv", html:
      `<b>Salary:</b> ${escapeHtml(row["Quote CTC"] || row["Salary Band"])}` }));
  }
  if (row.Location) {
    card.appendChild(ce("div", { class: "kv", html:
      `<b>Location:</b> ${escapeHtml(row.Location)}` }));
  }

  const status = (row.Status || "").trim();
  if (status) {
    const foot = ce("div", { class: "card-foot" }, [
      ce("span", { class: `pill ${statusPillClass(status)}`, text: status }),
    ]);
    card.appendChild(foot);
  }

  return card;
}

function renderUpcoming() {
  const list = document.getElementById("upcoming-list");
  if (!list) return;
  const interviewing = state.rows.filter(r => statusToColumn(r.Status) === "interview");
  list.innerHTML = "";
  if (!interviewing.length) {
    list.appendChild(ce("li", { class: "empty", text: "No upcoming interviews" }));
    return;
  }
  for (const r of interviewing.slice(0, 6)) {
    list.appendChild(ce("li", { text: `${r.Company} · ${r.Status}` }));
  }
}

function renderDetail(id) {
  const root = document.getElementById("view-root");
  root.innerHTML = "";
  const idx = state.rows.findIndex((r, i) => rowId(r, i) === id);
  if (idx < 0) {
    root.appendChild(ce("div", { class: "empty-detail", text: "Application not found." }));
    root.appendChild(ce("a", { class: "back-link", href: "#/" }, ["← Back to dashboard"]));
    return;
  }
  const row = state.rows[idx];

  root.appendChild(ce("a", { class: "back-link", href: "#/" }, ["← Back to dashboard"]));

  const head = ce("div", { class: "detail-head" }, [
    makeLogo(row),
    ce("div", { class: "who" }, [
      ce("h1", { text: row.Company || "—" }),
      ce("h2", { text: row["Role / Position"] || "" }),
      ce("div", { class: "meta" }, [
        row.Location ? ce("span", { text: row.Location }) : null,
        row["Date Applied"] ? ce("span", { text: "Applied " + row["Date Applied"] }) : null,
        row.Platform ? ce("span", { text: row.Platform }) : null,
        row.Tier ? ce("span", { text: row.Tier }) : null,
      ].filter(Boolean)),
    ]),
    row.Status ? ce("div", {}, [ce("span", { class: `pill ${statusPillClass(row.Status)}`, text: row.Status })]) : null,
  ].filter(Boolean));
  root.appendChild(head);

  const grid = ce("div", { class: "detail-grid" });
  const left = ce("div");
  const right = ce("div");

  // JD
  left.appendChild(section("Job Description",
    row["Role Summary (JD)"] || "(no description yet — paste JD via admin.html)",
    !row["Role Summary (JD)"]));

  // STAR Stories — two separate sections
  const starTech = row["STAR (Technical)"] || row["STAR Story"] || "";
  const starBeh  = row["STAR (Non-Technical)"] || "";
  left.appendChild(section("STAR Story — Technical",
    starTech || "(empty — add via admin.html)",
    !starTech));
  left.appendChild(section("STAR Story — Non-Technical / Behavioral",
    starBeh || "(empty — add via admin.html)",
    !starBeh));

  // Salary to Quote
  const salaryBody = [
    row["Quote CTC"] ? `Quote CTC: ${row["Quote CTC"]}` : null,
    row["Salary Band"] ? `Salary Band: ${row["Salary Band"]}` : null,
  ].filter(Boolean).join("\n");
  left.appendChild(section("Salary to Quote",
    salaryBody || "(no salary info)",
    !salaryBody));

  // Next Step + Notes
  if (row["Next Step"]) left.appendChild(section("Next Step", row["Next Step"]));
  if (row["Notes / Key Facts"]) left.appendChild(section("Notes", row["Notes / Key Facts"]));

  // Right: Chances gauge + metadata
  const fitPct = parsePct(row["Fit %"]);
  const chancesText = (row.Chances || "").trim();
  const gauge = ce("div", { class: "section" }, [
    ce("h3", { text: "Chances of Getting the Job" }),
    ce("div", { class: "gauge-wrap" }, [
      gaugeEl(fitPct ?? 0),
      ce("div", { class: "gauge-info" }, [
        ce("div", { html: fitPct != null ? `<b>Fit:</b> ${fitPct}%` : `<b>Fit:</b> not set` }),
        chancesText ? ce("div", { html: `<b>Chance:</b> ${escapeHtml(chancesText)}`, style: "margin-top: 6px;" }) : null,
      ].filter(Boolean)),
    ])
  ]);
  right.appendChild(gauge);

  // Metadata table
  const meta = ce("div", { class: "section" }, [
    ce("h3", { text: "Application Details" }),
    kvTable([
      ["Job ID / Req", row["Job ID / Req"]],
      ["Grade", row.Grade],
      ["Tier", row.Tier],
      ["Platform", row.Platform],
      ["Domain", row.Domain],
      ["Date Applied", row["Date Applied"]],
    ]),
  ]);
  right.appendChild(meta);

  grid.appendChild(left);
  grid.appendChild(right);
  root.appendChild(grid);
}

function section(title, body, isMuted = false) {
  return ce("div", { class: "section" }, [
    ce("h3", { text: title }),
    ce("div", { class: "body" + (isMuted ? " muted" : ""), text: body }),
  ]);
}

function gaugeEl(pct) {
  const p = Math.max(0, Math.min(100, pct || 0));
  const g = ce("div", { class: "gauge", style: `--pct:${p}` }, [
    ce("span", { class: "v", text: pct != null ? `${p}%` : "—" }),
  ]);
  return g;
}

function kvTable(pairs) {
  const t = ce("div", { class: "kv-table" });
  for (const [k, v] of pairs) {
    if (v == null || v === "") continue;
    t.appendChild(ce("div", { class: "row" }, [
      ce("div", { class: "k", text: k }),
      ce("div", { class: "v", text: String(v) }),
    ]));
  }
  return t;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

// ---- routing ----
function route() {
  const h = window.location.hash || "#/";
  const m = h.match(/^#\/app\/([^/]+)/);
  if (m) renderDetail(decodeURIComponent(m[1]));
  else renderDashboard();
}

window.addEventListener("hashchange", route);

// ---- gate ----
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
    sessionStorage.setItem("jt-pw", password);
    onUnlocked(payload);
  } catch (e) {
    errorEl.textContent = "Wrong password.";
    errorEl.hidden = false;
  }
}

function onUnlocked(payload) {
  state.rows = Array.isArray(payload.rows) ? payload.rows : [];
  state.updatedAt = payload.updated_at || null;
  document.getElementById("gate").hidden = true;
  document.getElementById("app").hidden = false;
  // sidebar nav clicks (only Dashboard is wired)
  document.querySelectorAll(".sidebar .nav li").forEach(li => {
    li.addEventListener("click", () => {
      document.querySelectorAll(".sidebar .nav li").forEach(x => x.classList.remove("active"));
      li.classList.add("active");
      window.location.hash = "#/";
    });
  });
  route();
}

document.getElementById("unlock-form").addEventListener("submit", (e) => {
  e.preventDefault();
  tryUnlock(document.getElementById("password").value);
});

// Auto-unlock if a session password is cached.
const cached = sessionStorage.getItem("jt-pw");
if (cached) tryUnlock(cached);
