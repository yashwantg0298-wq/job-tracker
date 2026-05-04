"""Parse the markdown table dump (sheet_raw.md) into rows.json for sync.py to encrypt."""
import json, re, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "state" / "sheet_raw.md"
OUT = ROOT / "state" / "rows.json"


def split_row(line: str) -> list[str]:
    parts = [p.strip() for p in line.strip().strip("|").split("|")]
    return parts


def main() -> int:
    text = RAW.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip().startswith("|")]
    if not lines:
        print("no table rows found")
        return 1

    header = split_row(lines[0])
    # Drop the leading "#" index column.
    keep_idx = [i for i, h in enumerate(header) if h not in {"\\#", "#"}]
    cols = [header[i] for i in keep_idx]

    rows: list[dict] = []
    for ln in lines[1:]:
        cells = split_row(ln)
        if len(cells) != len(header):
            continue
        # Skip the markdown alignment row (---/:-: cells).
        if all(re.fullmatch(r":?-+:?", c or "") for c in cells):
            continue
        # Skip rows where the first kept cell looks like a heading marker.
        row = {cols[i]: cells[orig] for i, orig in enumerate(keep_idx)}
        # Replace the markdown-escaped ampersand and skip empty Company rows.
        for k, v in list(row.items()):
            if isinstance(v, str):
                row[k] = v.replace("\\&", "&").replace("\\#", "#").strip()
        if not row.get("Company"):
            continue
        rows.append(row)

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"parsed {len(rows)} rows -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
