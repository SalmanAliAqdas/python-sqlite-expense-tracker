"""Regression checks for dashboard reporting and native Streamlit interactions."""

import csv
import os
import sqlite3
import unittest
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from dashboard_ui import monthly_data, savings_rate, summary_cards


APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


class DashboardReportingTests(unittest.TestCase):
    def test_savings_rate_and_summary_values(self):
        self.assertEqual(savings_rate(100000, 25000), Decimal("75"))
        self.assertEqual(savings_rate(100000, 120000), Decimal("-20"))
        self.assertEqual(savings_rate(100000, 0), Decimal("100"))
        self.assertIsNone(savings_rate(0, 25000))
        self.assertIsNone(savings_rate(0, 0))
        html = summary_cards({"income_paisa": 100000, "expense_paisa": 25000, "balance_paisa": 75000})
        for value in ("1,000.00", "250.00", "750.00", "75.0%"):
            self.assertIn(value, html)
        zero_html = summary_cards({"income_paisa": 0, "expense_paisa": 25000, "balance_paisa": -25000})
        self.assertIn("Add income to calculate", zero_html)
        self.assertIn("-250.00", zero_html)

    def test_monthly_data_keeps_exact_totals_and_fills_gaps(self):
        rows = [{"date": "2026-01-01", "kind": "Income", "amount_paisa": 10010},
                {"date": "2026-01-02", "kind": "Expense", "amount_paisa": 10},
                {"date": "2026-01-03", "kind": "Expense", "amount_paisa": 20},
                {"date": "2026-03-01", "kind": "Expense", "amount_paisa": 5500}]
        result = monthly_data(rows)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["Income"], 10010)
        self.assertEqual(result[0]["Expense"], 30)
        self.assertEqual(result[1]["Expense"], 0)
        self.assertEqual(result[1]["Month"], "2026-02-01")
        self.assertEqual(monthly_data([]), [])


class StreamlitInteractionTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"EXPENSE_TRACKER_MODE": "demo"})
        self.environment.start()
        self.apps = []
        self.app = self.new_app()

    def tearDown(self):
        for app in self.apps:
            if "tracker" in app.session_state:
                app.session_state["tracker"].close()
        self.environment.stop()

    def new_app(self):
        app = AppTest.from_file(APP, default_timeout=30).run()
        self.apps.append(app)
        self.assert_clean(app)
        return app

    def assert_clean(self, app=None):
        app = app or self.app
        self.assertEqual([item.message for item in app.exception], [])
        self.assertEqual([item.value for item in app.error], [])

    def navigate(self, key):
        self.app.button(key=f"nav_{key}").click().run()
        self.assert_clean()

    def save(self, kind, amount, description):
        self.navigate("add")
        self.app.get("button_group")[0].set_value(kind).run()
        self.app.text_input[0].set_value(amount)
        self.app.text_area[0].set_value(description)
        self.app.selectbox[0].set_value("Food" if kind == "Expense" else "Salary")
        self.app.date_input[0].set_value(date(2026, 10, 10))
        next(button for button in self.app.button if button.label == "Save transaction").click().run()
        self.assert_clean()

    def test_all_navigation_views_render_across_reruns(self):
        for key, title in (("analytics", "Analytics"), ("transactions", "Transactions"),
                           ("add", "Add transaction"), ("settings", "Settings"),
                           ("dashboard", "Expense Tracker")):
            with self.subTest(page=key):
                self.navigate(key)
                self.assertEqual(self.app.title[0].value, title)

    def test_add_income_expense_edit_delete_and_export(self):
        self.save("Income", "1000.10", "UI income")
        self.save("Expense", "200.20", "UI expense")
        tracker = self.app.session_state["tracker"]
        item = next(row for row in tracker.list_transactions() if row["description"] == "UI expense")
        self.navigate("transactions")
        self.app.selectbox(key="selected_transaction").set_value(f"Expense:{item['id']}").run()
        self.app.text_input[0].set_value("250.30")
        self.app.text_area[0].set_value("Updated UI expense")
        next(button for button in self.app.button if button.label == "Save changes").click().run()
        self.assert_clean()
        self.assertEqual(tracker.get_expense(item["id"])["amount_paisa"], 25030)
        self.app.selectbox(key="filter_kind").set_value("Expense").run()
        self.app.selectbox(key="filter_category").set_value("Food").run()
        self.app.date_input(key="filter_dates").set_value((date(2026, 10, 10), date(2026, 10, 10))).run()
        visible = self.app.dataframe[0].value
        self.assertIn("Updated UI expense", visible["Description"].tolist())
        self.assertTrue((visible["Type"] == "Expense").all())
        records = tracker.list_transactions("Food", "2026-10-10", "2026-10-10", "Expense")
        exported = list(csv.DictReader(StringIO(tracker.transactions_csv(records))))
        self.assertEqual(exported[0]["Description"], "Updated UI expense")
        self.assertEqual(exported[0]["Amount (PKR)"], "250.30")
        self.assertFalse(self.app.get("download_button")[0].proto.disabled)
        self.app.selectbox(key="selected_transaction").set_value(f"Expense:{item['id']}").run()
        self.assertTrue(self.app.button(key="delete_transaction").disabled)
        self.app.checkbox[0].check().run()
        self.app.button(key="delete_transaction").click().run()
        self.assert_clean()
        self.assertIsNone(tracker.get_expense(item["id"]))
        self.assertTrue(any("deleted" in element.value for element in self.app.success))

    def test_invalid_input_and_database_errors_preserve_form(self):
        self.navigate("add")
        self.app.text_input[0].set_value("-10")
        self.app.text_area[0].set_value("Retain my description")
        next(button for button in self.app.button if button.label == "Save transaction").click().run()
        self.assertTrue(self.app.warning)
        self.assertEqual(self.app.text_area[0].value, "Retain my description")
        self.app.text_input[0].set_value("10")
        tracker = self.app.session_state["tracker"]
        with patch.object(tracker.db, "execute", side_effect=sqlite3.OperationalError("private database details")):
            next(button for button in self.app.button if button.label == "Save transaction").click().run()
        self.assertEqual(len(self.app.error), 1)
        self.assertNotIn("private database details", self.app.error[0].value)
        self.assertEqual(self.app.text_area[0].value, "Retain my description")
        self.assertFalse(self.app.exception)

    def test_demo_sessions_are_isolated_and_reset_needs_confirmation(self):
        second = self.new_app()
        other_tracker = second.session_state["tracker"]
        original = other_tracker.list_transactions()
        self.save("Expense", "5.50", "Only in the first session")
        self.assertEqual(other_tracker.list_transactions(), original)
        self.navigate("settings")
        self.assertTrue(self.app.button(key="reset_demo").disabled)
        self.app.checkbox(key="confirm_demo_reset").check().run()
        self.app.button(key="reset_demo").click().run()
        self.assert_clean()
        self.assertFalse(any(row["description"] == "Only in the first session"
                             for row in self.app.session_state["tracker"].list_transactions()))
        self.assertEqual(other_tracker.list_transactions(), original)
        self.assertTrue(self.app.button(key="reset_demo").disabled)

    def test_analytics_filter_and_empty_workspace(self):
        self.navigate("analytics")
        tracker = self.app.session_state["tracker"]
        period = min(row["date"][:7] for row in tracker.list_transactions())
        self.app.selectbox(key="analytics_period").set_value(period).run()
        self.assert_clean()
        self.assertEqual(len(self.app.dataframe[0].value), 1)
        tracker.db.execute("DELETE FROM expenses")
        tracker.db.execute("DELETE FROM incomes")
        self.navigate("dashboard")
        self.assertTrue(any("Add income to calculate" in element.value for element in self.app.markdown))
        self.navigate("transactions")
        self.assertTrue(self.app.get("download_button")[0].proto.disabled)
        self.navigate("analytics")
        self.assertEqual(self.app.selectbox(key="analytics_period").value, "All time")


if __name__ == "__main__":
    unittest.main()
