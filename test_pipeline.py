"""Offline tests. No API key, no network - these check the parts that must
never break: PDF reading, schema validation, and the reconciliation math.

    python test_pipeline.py
"""
import re
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import pdfplumber                      # noqa: E402
from pydantic import ValidationError   # noqa: E402
from schema import Statement           # noqa: E402

SAMPLE = ROOT / "sample_statement.pdf"
ROW = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(-?[\d,]+\.\d{2})\s+([\d,]+\.\d{2})$")


def num(s):
    return Decimal(s.replace(",", ""))


def parse_sample() -> dict:
    """Deterministic parser standing in for the model's JSON output."""
    with pdfplumber.open(SAMPLE) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    opening = num(re.search(r"Opening balance:\s*([\d,]+\.\d{2})", text).group(1))
    closing = num(re.search(r"Closing balance:\s*([\d,]+\.\d{2})", text).group(1))

    txns = []
    for line in text.splitlines():
        m = ROW.match(line.strip())
        if not m:
            continue
        d, desc, amount, balance = m.groups()
        mm, dd, yyyy = d.split("/")
        txns.append({
            "date": f"{yyyy}-{mm}-{dd}",
            "description": desc.strip(),
            "amount": str(num(amount)),
            "balance": str(num(balance)),
            "category": "Other",
        })

    return {
        "bank_name": "NORTHWIND COMMERCIAL BANK",
        "account_holder": "Meridian Logistics LLC",
        "account_number_masked": "****-****-4471",
        "currency": "USD",
        "period_start": "2026-05-01",
        "period_end": "2026-05-31",
        "opening_balance": str(opening),
        "closing_balance": str(closing),
        "transactions": txns,
    }


def check(label, cond):
    print(f"  [{'ok ' if cond else 'FAIL'}] {label}")
    return cond


def main() -> int:
    print("test_pipeline")
    ok = True

    payload = parse_sample()
    statement = Statement.model_validate(payload)
    ok &= check(f"parsed {len(statement.transactions)} transactions",
                len(statement.transactions) == 34)
    ok &= check("signed amounts (debits negative, credits positive)",
                any(t.amount < 0 for t in statement.transactions)
                and any(t.amount > 0 for t in statement.transactions))

    r = statement.reconcile()
    ok &= check(f"reconciliation passes (diff {r['difference']})", r["passed"])

    # A statement whose closing balance does not match must be caught.
    bad = dict(payload, closing_balance="1.00")
    ok &= check("wrong closing balance is flagged",
                not Statement.model_validate(bad).reconcile()["passed"])

    # Garbage from the model must not slip through.
    try:
        Statement.model_validate(
            dict(payload, transactions=[{"date": "not-a-date",
                                         "description": "x", "amount": "1"}]))
        ok &= check("invalid date rejected", False)
    except ValidationError:
        ok &= check("invalid date rejected", True)

    print("PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
