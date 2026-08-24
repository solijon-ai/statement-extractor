"""Generate a synthetic bank statement PDF for demo purposes.

No real account data is used anywhere in this project. Every name, number and
transaction below is invented for testing the extractor.
"""
import random
from datetime import date, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle)

random.seed(7)

MERCHANTS = [
    ("AMZN Mktp US*RT4K9", "Shopping"),
    ("STRIPE PAYOUT", "Income"),
    ("UBER TRIP 8821", "Transport"),
    ("DIGITALOCEAN.COM", "Software"),
    ("WHOLEFDS MKT 10238", "Groceries"),
    ("ATM WITHDRAWAL 4417", "Cash"),
    ("GITHUB INC", "Software"),
    ("DELTA AIR 0062119", "Travel"),
    ("SQ *BLUE BOTTLE COFFEE", "Dining"),
    ("PAYROLL DEPOSIT NORTHWIND", "Income"),
    ("VERIZON WIRELESS PMT", "Utilities"),
    ("NETFLIX.COM", "Subscriptions"),
]


def build_rows(start: date, n: int, opening: float):
    rows, balance, day = [], opening, start
    for _ in range(n):
        day += timedelta(days=random.randint(0, 3))
        desc, _cat = random.choice(MERCHANTS)
        if "PAYOUT" in desc or "PAYROLL" in desc:
            amount = round(random.uniform(800, 4200), 2)
        else:
            amount = -round(random.uniform(6, 640), 2)
        balance = round(balance + amount, 2)
        rows.append([
            day.strftime("%m/%d/%Y"),
            desc,
            f"{amount:,.2f}" if amount < 0 else "",
            f"{amount:,.2f}" if amount > 0 else "",
            f"{balance:,.2f}",
        ])
    return rows, balance


def main(path="sample_statement.pdf"):
    opening = 12_480.55
    rows, closing = build_rows(date(2026, 5, 1), 34, opening)

    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8.5,
                           leading=11, textColor=colors.HexColor("#333333"))
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=18 * mm,
                            bottomMargin=18 * mm, leftMargin=16 * mm,
                            rightMargin=16 * mm, title="Account Statement")

    story = [
        Paragraph("NORTHWIND COMMERCIAL BANK", styles["Title"]),
        Paragraph("Account Statement &mdash; Business Checking", styles["Heading3"]),
        Spacer(1, 6),
        Paragraph(
            "Account holder: Meridian Logistics LLC<br/>"
            "Account number: ****-****-4471<br/>"
            "Statement period: May 1, 2026 &ndash; May 31, 2026<br/>"
            "Currency: USD", small),
        Spacer(1, 10),
        Paragraph(
            f"Opening balance: {opening:,.2f} &nbsp;&nbsp; "
            f"Closing balance: {closing:,.2f}", small),
        Spacer(1, 12),
    ]

    header = ["Date", "Description", "Debit", "Credit", "Balance"]
    table = Table([header] + rows, repeatRows=1,
                  colWidths=[24 * mm, 72 * mm, 24 * mm, 24 * mm, 26 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f2f5f9")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8d2de")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(table)
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "This is a synthetic document generated for software testing. "
        "It does not represent a real account.", small))

    doc.build(story)
    print(f"wrote {path} ({len(rows)} transactions, closing {closing:,.2f})")


if __name__ == "__main__":
    main()
