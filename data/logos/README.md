# Custom company logos

Drop a PNG (or SVG) here named `<company-slug>.png` and the dashboard will
prefer it over network-fetched logos. The slug is the lowercase company
name with non-alphanumerics replaced by hyphens. Examples:

- "JPMorgan Chase" → `jpmorgan-chase.png`
- "EY India" → `ey-india.png`
- "CRISIL (S&P Global)" → `crisil-s-p-global.png`

Recommended: 256×256 px, transparent or white background. Square images
look cleanest in the 32px Kanban cards and 64px detail header.

Alternative: set the **Logo URL (override)** field per-row in admin.html
to point at any direct image URL — that takes priority over both this
folder and the network fallbacks.
