"""Interactive terminal interface for Python Expense Tracker."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from expense_tracker import ExpenseTracker, format_pkr


DATABASE_PATH = Path(__file__).resolve().parent / "expense_tracker.db"
REPORT_OPTIONS = {"2", "5", "6", "7"}


def read_id(prompt: str = "Expense ID: ") -> int:
    value = input(prompt).strip()
    if not value.isdigit() or int(value) < 1:
        raise ValueError("Please enter a valid positive ID.")
    return int(value)


def display_expenses(expenses: list[dict]) -> None:
    if not expenses:
        print("\nNo expenses found.")
        return
    print("\n{:<6} {:<12} {:<18} {:<32} {:>16}".format("ID", "Date", "Category", "Description", "Amount"))
    print("-" * 90)
    for item in expenses:
        description = item["description"][:29] + "..." if len(item["description"]) > 32 else item["description"]
        print(f'{item["id"]:<6} {item["date"]:<12} {item["category"]:<18.18} {description:<32} {format_pkr(item["amount_paisa"]):>16}')
    total = sum(item["amount_paisa"] for item in expenses)
    print("-" * 90)
    print(f"Total: {format_pkr(total)} ({len(expenses)} expense(s))")


def view_all_expenses(tracker: ExpenseTracker) -> None:
    """Retrieve every saved expense and display it in the terminal."""
    print("\n--- View All Expenses ---")
    expenses = tracker.list_expenses()
    display_expenses(expenses)


def pause_before_menu() -> None:
    """Keep report output visible until the user is ready for the menu."""
    input("\nPress Enter to return to the main menu...")


def choose_category(tracker: ExpenseTracker, allow_blank: bool = False) -> str | None:
    categories = tracker.list_categories()
    print("Categories: " + ", ".join(categories))
    prompt = "Category (or type a new one)"
    if allow_blank:
        prompt += " [leave blank to keep current]"
    value = input(prompt + ": ").strip()
    return value or None if allow_blank else value


def add_expense(tracker: ExpenseTracker) -> None:
    print("\n--- Add Expense ---")
    amount = input("Amount (PKR): ").strip()
    category = choose_category(tracker)
    description = input("Description: ").strip()
    entered_date = input(f"Date [YYYY-MM-DD, default {date.today().isoformat()}]: ").strip()
    expense_id = tracker.add_expense(amount, category or "", description, entered_date or None)
    print(f"Expense #{expense_id} added successfully.")


def edit_expense(tracker: ExpenseTracker) -> None:
    print("\n--- Edit Expense ---")
    expense_id = read_id()
    current = tracker.get_expense(expense_id)
    if not current:
        print("No expense exists with that ID.")
        return
    print("Press Enter to keep the current value.")
    amount = input(f"Amount [{format_pkr(current['amount_paisa'])}]: ").strip()
    category = choose_category(tracker, allow_blank=True)
    description = input(f"Description [{current['description']}]: ").strip()
    expense_date = input(f"Date [{current['date']}]: ").strip()
    tracker.edit_expense(expense_id, amount or None, category, description or None, expense_date or None)
    print(f"Expense #{expense_id} updated successfully.")


def delete_expense(tracker: ExpenseTracker) -> None:
    print("\n--- Delete Expense ---")
    expense_id = read_id()
    current = tracker.get_expense(expense_id)
    if not current:
        print("No expense exists with that ID.")
        return
    print(f"Delete #{expense_id}: {current['description']} ({format_pkr(current['amount_paisa'])})?")
    if input("Type Y to confirm: ").strip().lower() == "y":
        tracker.delete_expense(expense_id)
        print("Expense deleted successfully.")
    else:
        print("Deletion cancelled.")


def monthly_summary(tracker: ExpenseTracker) -> None:
    print("\n--- Monthly Summary ---")
    year = int(input("Year (for example 2026): ").strip())
    month = int(input("Month (1-12): ").strip())
    summary = tracker.monthly_summary(year, month)
    print(f"\nSummary for {year:04d}-{month:02d}")
    print(f"Expenses: {summary['count']}")
    print(f"Total: {format_pkr(summary['total_paisa'])}")
    if summary["by_category"]:
        print("By category:")
        for category, total in summary["by_category"].items():
            print(f"  {category:<20} {format_pkr(total)}")


def category_summary(tracker: ExpenseTracker) -> None:
    print("\n--- Category Summary ---")
    rows = tracker.category_summary()
    if not rows:
        print("No expenses found.")
        return
    for row in rows:
        print(f"{row['category']:<20} {format_pkr(row['total_paisa']):>16}  ({row['count']} expense(s))")


def search(tracker: ExpenseTracker) -> None:
    print("\n--- Search and Filter ---")
    print("Leave any filter blank to ignore it.")
    description = input("Description contains: ").strip()
    category = input("Category: ").strip()
    start_date = input("Start date (YYYY-MM-DD): ").strip()
    end_date = input("End date (YYYY-MM-DD): ").strip()
    display_expenses(tracker.search_expenses(description or None, category or None,
                                             start_date or None, end_date or None))


def export(tracker: ExpenseTracker) -> None:
    print("\n--- Export to CSV ---")
    default = f"expenses_{date.today().isoformat()}.csv"
    name = input(f"File name [{default}]: ").strip() or default
    path = Path(name)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    count = tracker.export_csv(path)
    print(f"Exported {count} expense(s) to: {path}")


def main() -> None:
    actions = {
        "1": add_expense,
        "2": view_all_expenses,
        "3": edit_expense,
        "4": delete_expense,
        "5": monthly_summary,
        "6": category_summary,
        "7": search,
        "8": export,
    }
    with ExpenseTracker(DATABASE_PATH) as tracker:
        while True:
            print("""
=================================
     PYTHON EXPENSE TRACKER
=================================
1. Add Expense
2. View All Expenses
3. Edit Expense
4. Delete Expense
5. Monthly Summary
6. Category Summary
7. Search and Filter
8. Export to CSV
9. Exit
""")
            choice = input("Choose an option (1-9): ").strip()
            if choice == "9":
                print("Goodbye!")
                break
            action = actions.get(choice)
            if action is None:
                print("Please choose a number from 1 to 9.")
                continue
            try:
                action(tracker)
                if choice in REPORT_OPTIONS:
                    pause_before_menu()
            except (ValueError, OSError) as error:
                print(f"Error: {error}")
            except KeyboardInterrupt:
                print("\nOperation cancelled.")


if __name__ == "__main__":
    main()
