"""Business logic for managing and reporting personal expenses."""

from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from database import Database


EXPENSE_SELECT = """
SELECT e.id, e.expense_date AS date, c.name AS category,
       e.description, e.amount_paisa
FROM expenses e
JOIN categories c ON c.id = e.category_id
"""


def amount_to_paisa(value: str | int | Decimal) -> int:
    """Convert a PKR value to integer paisa with two-decimal rounding."""
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as error:
        raise ValueError("Amount must be a valid number.") from error
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    return int(amount * 100)


def format_pkr(amount_paisa: int) -> str:
    return f"PKR {Decimal(amount_paisa) / 100:,.2f}"


def validate_date(value: str | None) -> str:
    text = value.strip() if value else date.today().isoformat()
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError as error:
        raise ValueError("Date must use YYYY-MM-DD format.") from error


class ExpenseTracker:
    """Application service used by both the CLI and automated tests."""

    def __init__(self, database_path: str | Path = "expense_tracker.db") -> None:
        self.db = Database(database_path)

    def close(self) -> None:
        self.db.close()

    def list_categories(self) -> list[str]:
        rows = self.db.fetchall("SELECT name FROM categories ORDER BY name COLLATE NOCASE")
        return [row["name"] for row in rows]

    def add_category(self, name: str) -> str:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Category name cannot be empty.")
        self.db.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cleaned,))
        row = self.db.fetchone(
            "SELECT name FROM categories WHERE name = ? COLLATE NOCASE", (cleaned,)
        )
        return str(row["name"])

    def _category_id(self, category: str, create: bool = True) -> int:
        cleaned = category.strip()
        if not cleaned:
            raise ValueError("Category cannot be empty.")
        row = self.db.fetchone(
            "SELECT id FROM categories WHERE name = ? COLLATE NOCASE", (cleaned,)
        )
        if row is None and create:
            self.add_category(cleaned)
            row = self.db.fetchone(
                "SELECT id FROM categories WHERE name = ? COLLATE NOCASE", (cleaned,)
            )
        if row is None:
            raise ValueError(f"Unknown category: {cleaned}")
        return int(row["id"])

    def add_expense(
        self, amount: str | int | Decimal, category: str, description: str, expense_date: str | None = None
    ) -> int:
        cleaned_description = description.strip()
        if not cleaned_description:
            raise ValueError("Description cannot be empty.")
        cursor = self.db.execute(
            "INSERT INTO expenses (amount_paisa, category_id, description, expense_date) VALUES (?, ?, ?, ?)",
            (amount_to_paisa(amount), self._category_id(category), cleaned_description, validate_date(expense_date)),
        )
        return int(cursor.lastrowid)

    def get_expense(self, expense_id: int) -> dict[str, Any] | None:
        row = self.db.fetchone(EXPENSE_SELECT + " WHERE e.id = ?", (expense_id,))
        return dict(row) if row else None

    def list_expenses(self) -> list[dict[str, Any]]:
        rows = self.db.fetchall(EXPENSE_SELECT + " ORDER BY e.expense_date DESC, e.id DESC")
        return [dict(row) for row in rows]

    def edit_expense(
        self,
        expense_id: int,
        amount: str | int | Decimal | None = None,
        category: str | None = None,
        description: str | None = None,
        expense_date: str | None = None,
    ) -> bool:
        existing = self.get_expense(expense_id)
        if existing is None:
            return False
        amount_paisa = existing["amount_paisa"] if amount is None else amount_to_paisa(amount)
        category_id = self._category_id(existing["category"] if category is None else category)
        new_description = existing["description"] if description is None else description.strip()
        if not new_description:
            raise ValueError("Description cannot be empty.")
        new_date = existing["date"] if expense_date is None else validate_date(expense_date)
        self.db.execute(
            "UPDATE expenses SET amount_paisa = ?, category_id = ?, description = ?, expense_date = ? WHERE id = ?",
            (amount_paisa, category_id, new_description, new_date, expense_id),
        )
        return True

    def delete_expense(self, expense_id: int) -> bool:
        cursor = self.db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        return cursor.rowcount > 0

    def search_expenses(
        self, description: str | None = None, category: str | None = None,
        start_date: str | None = None, end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        parameters: list[Any] = []
        if description:
            conditions.append("e.description LIKE ?")
            parameters.append(f"%{description.strip()}%")
        if category:
            conditions.append("c.name = ? COLLATE NOCASE")
            parameters.append(category.strip())
        if start_date:
            conditions.append("e.expense_date >= ?")
            parameters.append(validate_date(start_date))
        if end_date:
            conditions.append("e.expense_date <= ?")
            parameters.append(validate_date(end_date))
        if start_date and end_date and validate_date(start_date) > validate_date(end_date):
            raise ValueError("Start date cannot be after end date.")
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        rows = self.db.fetchall(EXPENSE_SELECT + where + " ORDER BY e.expense_date DESC, e.id DESC", parameters)
        return [dict(row) for row in rows]

    def monthly_summary(self, year: int, month: int) -> dict[str, Any]:
        if year < 1 or not 1 <= month <= 12:
            raise ValueError("Enter a valid year and a month from 1 to 12.")
        prefix = f"{year:04d}-{month:02d}"
        totals = self.db.fetchone(
            "SELECT COALESCE(SUM(amount_paisa), 0) total, COUNT(*) count FROM expenses WHERE substr(expense_date, 1, 7) = ?",
            (prefix,),
        )
        rows = self.db.fetchall(
            """SELECT c.name category, SUM(e.amount_paisa) total
               FROM expenses e JOIN categories c ON c.id = e.category_id
               WHERE substr(e.expense_date, 1, 7) = ?
               GROUP BY c.id ORDER BY total DESC, c.name""",
            (prefix,),
        )
        return {"total_paisa": int(totals["total"]), "count": int(totals["count"]),
                "by_category": {row["category"]: int(row["total"]) for row in rows}}

    def category_summary(self) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            """SELECT c.name category, COUNT(e.id) count,
                      COALESCE(SUM(e.amount_paisa), 0) total_paisa
               FROM categories c JOIN expenses e ON e.category_id = c.id
               GROUP BY c.id ORDER BY total_paisa DESC, c.name"""
        )
        return [dict(row) for row in rows]

    def total(self, expenses: list[dict[str, Any]] | None = None) -> int:
        records = self.list_expenses() if expenses is None else expenses
        return sum(int(item["amount_paisa"]) for item in records)

    def export_csv(self, file_path: str | Path, expenses: list[dict[str, Any]] | None = None) -> int:
        records = self.list_expenses() if expenses is None else expenses
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["ID", "Date", "Category", "Description", "Amount (PKR)"])
            for item in records:
                writer.writerow([item["id"], item["date"], item["category"], item["description"],
                                 f'{Decimal(item["amount_paisa"]) / 100:.2f}'])
        return len(records)

    def __enter__(self) -> "ExpenseTracker":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
