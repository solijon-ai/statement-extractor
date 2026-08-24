"""Output schema. The whole point of the tool: the model may hallucinate,
the schema does not. Anything that does not validate is rejected loudly."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

Category = Literal[
    "Income", "Transfer", "Groceries", "Dining", "Transport", "Travel",
    "Software", "Utilities", "Subscriptions", "Fees", "Cash", "Shopping",
    "Other",
]


class Transaction(BaseModel):
    date: date
    description: str = Field(min_length=1)
    amount: Decimal = Field(
        description="Signed: negative for money out, positive for money in.")
    balance: Optional[Decimal] = None
    category: Category = "Other"


class Statement(BaseModel):
    bank_name: Optional[str] = None
    account_holder: Optional[str] = None
    account_number_masked: Optional[str] = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    transactions: List[Transaction] = Field(default_factory=list)

    @property
    def total_in(self) -> Decimal:
        return sum((t.amount for t in self.transactions if t.amount > 0),
                   Decimal("0"))

    @property
    def total_out(self) -> Decimal:
        return sum((t.amount for t in self.transactions if t.amount < 0),
                   Decimal("0"))

    @model_validator(mode="after")
    def _period_order(self) -> "Statement":
        if self.period_start and self.period_end:
            if self.period_end < self.period_start:
                raise ValueError("period_end is earlier than period_start")
        return self

    def reconcile(self, tolerance: Decimal = Decimal("0.01")) -> dict:
        """Arithmetic check: opening + net movement should equal closing.

        This is what makes the output trustworthy. If the numbers do not add
        up, the extraction is flagged instead of quietly shipped.
        """
        if self.opening_balance is None or self.closing_balance is None:
            return {"checked": False, "reason": "missing opening/closing balance"}
        expected = self.opening_balance + self.total_in + self.total_out
        delta = (expected - self.closing_balance).copy_abs()
        return {
            "checked": True,
            "passed": delta <= tolerance,
            "expected_closing": str(expected),
            "reported_closing": str(self.closing_balance),
            "difference": str(delta),
        }
