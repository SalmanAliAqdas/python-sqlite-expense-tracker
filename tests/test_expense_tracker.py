import csv
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from expense_tracker import ExpenseTracker, amount_to_paisa
from main import display_expenses, main, pause_before_menu, view_all_expenses


class ExpenseTrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tracker = ExpenseTracker(Path(self.temp_dir.name) / "test.db")

    def tearDown(self):
        self.tracker.close()
        self.temp_dir.cleanup()

    def test_add_expense_and_money_accuracy(self):
        expense_id = self.tracker.add_expense("1250.55", "Food", "Groceries", "2026-10-05")
        expense = self.tracker.get_expense(expense_id)
        self.assertEqual(expense["amount_paisa"], 125055)
        self.assertEqual(expense["category"], "Food")
        self.assertEqual(amount_to_paisa("0.10") + amount_to_paisa("0.20"), 30)

    def test_rejects_invalid_expense_values(self):
        for amount in ("0", "-1", "not a number"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                self.tracker.add_expense(amount, "Food", "Invalid")
        with self.assertRaises(ValueError):
            self.tracker.add_expense("10", "Food", "", "2026-10-05")
        with self.assertRaises(ValueError):
            self.tracker.add_expense("10", "Food", "Test", "05/10/2026")

    def test_custom_category_and_edit(self):
        expense_id = self.tracker.add_expense("100", "Pets", "Food", "2026-09-01")
        changed = self.tracker.edit_expense(expense_id, "150.25", "Animal Care", "Vet", "2026-09-02")
        self.assertTrue(changed)
        expense = self.tracker.get_expense(expense_id)
        self.assertEqual(expense["amount_paisa"], 15025)
        self.assertEqual(expense["category"], "Animal Care")
        self.assertEqual(expense["description"], "Vet")
        self.assertFalse(self.tracker.edit_expense(999, amount="10"))

    def test_delete(self):
        expense_id = self.tracker.add_expense("25", "Transport", "Bus")
        self.assertTrue(self.tracker.delete_expense(expense_id))
        self.assertIsNone(self.tracker.get_expense(expense_id))
        self.assertFalse(self.tracker.delete_expense(expense_id))

    def test_search_and_filters(self):
        self.tracker.add_expense("500", "Food", "Weekly groceries", "2026-10-01")
        self.tracker.add_expense("200", "Transport", "Bus pass", "2026-10-10")
        self.tracker.add_expense("300", "Food", "Dinner", "2026-11-01")
        self.assertEqual(len(self.tracker.search_expenses(description="grocer")), 1)
        self.assertEqual(len(self.tracker.search_expenses(category="food")), 2)
        results = self.tracker.search_expenses(start_date="2026-10-02", end_date="2026-10-31")
        self.assertEqual([item["description"] for item in results], ["Bus pass"])
        with self.assertRaises(ValueError):
            self.tracker.search_expenses(start_date="2026-12-01", end_date="2026-01-01")

    def test_monthly_and_category_calculations(self):
        self.tracker.add_expense("100.10", "Food", "One", "2026-10-01")
        self.tracker.add_expense("200.20", "Food", "Two", "2026-10-31")
        self.tracker.add_expense("50", "Bills", "Three", "2026-10-10")
        self.tracker.add_expense("999", "Food", "Other month", "2026-11-01")
        summary = self.tracker.monthly_summary(2026, 10)
        self.assertEqual(summary["total_paisa"], 35030)
        self.assertEqual(summary["count"], 3)
        self.assertEqual(summary["by_category"], {"Food": 30030, "Bills": 5000})
        categories = {row["category"]: row for row in self.tracker.category_summary()}
        self.assertEqual(categories["Food"]["total_paisa"], 129930)

    def test_sorting_and_csv_export(self):
        self.tracker.add_expense("20", "Other", "Older", "2026-01-01")
        self.tracker.add_expense("10", "Other", "Newer", "2026-02-01")
        self.assertEqual([e["description"] for e in self.tracker.list_expenses()], ["Newer", "Older"])
        output = Path(self.temp_dir.name) / "expenses.csv"
        self.assertEqual(self.tracker.export_csv(output), 2)
        with output.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(rows[0], ["ID", "Date", "Category", "Description", "Amount (PKR)"])
        self.assertEqual(rows[1][-1], "10.00")


class ViewAllExpensesTests(unittest.TestCase):
    def test_display_expenses_shows_every_column_and_total(self):
        expenses = [{
            "id": 7,
            "date": "2026-10-18",
            "category": "Food",
            "description": "Family dinner",
            "amount_paisa": 125050,
        }]

        output = StringIO()
        with redirect_stdout(output):
            display_expenses(expenses)

        text = output.getvalue()
        for expected in ("ID", "Date", "Category", "Description", "Amount"):
            self.assertIn(expected, text)
        for expected in ("7", "2026-10-18", "Food", "Family dinner", "PKR 1,250.50"):
            self.assertIn(expected, text)
        self.assertIn("Total: PKR 1,250.50 (1 expense(s))", text)

    def test_view_all_expenses_shows_friendly_empty_message(self):
        tracker = MagicMock()
        tracker.list_expenses.return_value = []

        output = StringIO()
        with redirect_stdout(output):
            view_all_expenses(tracker)

        tracker.list_expenses.assert_called_once_with()
        self.assertIn("View All Expenses", output.getvalue())
        self.assertIn("No expenses found.", output.getvalue())

    @patch("main.ExpenseTracker")
    @patch("builtins.input", side_effect=["2", "", "9"])
    def test_menu_option_2_calls_view_all_expenses(self, mock_input, tracker_class):
        tracker = MagicMock()
        tracker.list_expenses.return_value = [{
            "id": 3,
            "date": "2026-08-09",
            "category": "Bills",
            "description": "Electricity",
            "amount_paisa": 450000,
        }]
        tracker_class.return_value.__enter__.return_value = tracker

        output = StringIO()
        with redirect_stdout(output):
            main()

        tracker.list_expenses.assert_called_once_with()
        self.assertIn("Electricity", output.getvalue())
        self.assertIn("PKR 4,500.00", output.getvalue())
        mock_input.assert_any_call("\nPress Enter to return to the main menu...")

    @patch("builtins.input", return_value="")
    def test_report_pause_waits_for_enter(self, mock_input):
        pause_before_menu()
        mock_input.assert_called_once_with("\nPress Enter to return to the main menu...")


if __name__ == "__main__":
    unittest.main()
