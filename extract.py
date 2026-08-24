"""Bank statement / invoice PDF -> validated structured data.

Usage:
    export ANTHROPIC_API_KEY=sk-...
    python extract.py sample_statement.pdf --out output/

Handles both digital PDFs (text layer) and scans (page images sent to the
model as vision input). Output is validated against schema.py and
arithmetically reconciled before it is written.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path

import pdfplumber
from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema import Statement  # noqa: E402

MODEL = "claude-sonnet-4-6"
MIN_CHARS_FOR_TEXT_MODE = 200

SYSTEM = """You extract structured data from bank statements and invoices.

Rules:
- Return ONLY a JSON object. No prose, no markdown fences.
- amount is SIGNED: negative for money leaving the account (debit),
  positive for money arriving (credit).
- Copy descriptions verbatim from the document. Do not clean them up.
- Dates as YYYY-MM-DD.
- If a field is not present in the document, use null. Never invent a value.
- category must be one of: Income, Transfer, Groceries, Dining, Transport,
  Travel, Software, Utilities, Subscriptions, Fees, Cash, Shopping, Other.

Shape:
{"bank_name": str|null, "account_holder": str|null,
 "account_number_masked": str|null, "currency": "USD",
 "period_start": "YYYY-MM-DD"|null, "period_end": "YYYY-MM-DD"|null,
 "opening_balance": number|null, "closing_balance": number|null,
 "transactions": [{"date": "YYYY-MM-DD", "description": str,
                   "amount": number, "balance": number|null,
                   "category": str}]}"""


def read_pdf(path: Path) -> tuple[str, list[bytes]]:
    """Return (text, page_png_bytes). Images only produced for scans."""
    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
        text = "\n".join(text_parts).strip()
        if len(text) >= MIN_CHARS_FOR_TEXT_MODE:
            return text, []
        images = []
        for page in pdf.pages[:8]:          # vision cap, keeps cost sane
            buf = io.BytesIO()
            page.to_image(resolution=150).original.save(buf, format="PNG")
            images.append(buf.getvalue())
    return text, images


def build_content(text: str, images: list[bytes]) -> list[dict]:
    if images:
        content = [{"type": "image",
                    "source": {"type": "base64", "media_type": "image/png",
                               "data": base64.b64encode(img).decode()}}
                   for img in images]
        content.append({"type": "text",
                        "text": "Extract this statement as JSON."})
        return content
    return [{"type": "text",
             "text": f"Extract this statement as JSON.\n\n<document>\n{text}\n</document>"}]


def strip_fences(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def extract(path: Path) -> tuple[Statement, dict]:
    text, images = read_pdf(path)
    mode = "vision (scan)" if images else "text layer"
    print(f"  source        : {path.name}  [{mode}]")

    client = Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM,
        messages=[{"role": "user", "content": build_content(text, images)}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text")
    data = json.loads(strip_fences(raw))
    statement = Statement.model_validate(data)
    usage = {"input_tokens": resp.usage.input_tokens,
             "output_tokens": resp.usage.output_tokens}
    return statement, usage


def write_csv(statement: Statement, path: Path) -> None:
    import csv
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "description", "amount", "balance", "category"])
        for t in statement.transactions:
            w.writerow([t.date, t.description, t.amount, t.balance, t.category])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--out", type=Path, default=Path("output"))
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    statement, usage = extract(args.pdf)

    check = statement.reconcile()
    stem = args.pdf.stem
    (args.out / f"{stem}.json").write_text(
        statement.model_dump_json(indent=2), encoding="utf-8")
    write_csv(statement, args.out / f"{stem}.csv")

    print(f"  transactions  : {len(statement.transactions)}")
    print(f"  money in      : {statement.total_in}")
    print(f"  money out     : {statement.total_out}")
    if check.get("checked"):
        verdict = "PASS" if check["passed"] else "FAIL"
        print(f"  reconciliation: {verdict} "
              f"(expected {check['expected_closing']}, "
              f"reported {check['reported_closing']})")
    else:
        print(f"  reconciliation: skipped ({check['reason']})")
    print(f"  tokens        : {usage['input_tokens']} in / "
          f"{usage['output_tokens']} out")
    print(f"  written       : {args.out}/{stem}.json, {args.out}/{stem}.csv")
    return 0 if check.get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
