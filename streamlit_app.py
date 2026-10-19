"""Session-isolated Streamlit interface for the existing expense tracker."""

from __future__ import annotations

import os
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import streamlit as st

from expense_tracker import ExpenseTracker, format_pkr


st.set_page_config(page_title="Expense Tracker", page_icon="💸", layout="wide")

st.markdown("""
<style>
    .stApp {background: #f6f8fb; color: #172338;}
    .block-container {max-width: 1260px; padding-top: 2rem; padding-bottom: 3rem;}
    h1, h2, h3 {letter-spacing: -.035em; color: #172338;}
    h1 {font-weight: 750;}
    [data-testid="stMetric"] {background: white; border: 1px solid #e5eaf1;
        border-radius: 16px; padding: 1rem 1.2rem; box-shadow: 0 5px 22px #233e6610;}
    [data-testid="stMetricLabel"] {color: #607089;}
    [data-testid="stMetricValue"] {color: #163c66;}
    [data-testid="stSidebar"] {background: #edf3f9;}
    div.stButton > button[kind="primary"] {background: #176b87; border-color: #176b87;}
    .eyebrow {color: #176b87; font-weight: 700; letter-spacing: .12em;
        text-transform: uppercase; font-size: .72rem;}
    .subtitle {color: #617188; margin-top: -.4rem; margin-bottom: 1.6rem;}
    @media (max-width: 700px) {.block-container {padding: 1rem .9rem 2rem;}}
</style>
""", unsafe_allow_html=True)


def seed_demo(tracker: ExpenseTracker) -> None:
    """Create fictional transactions in this session's in-memory database."""
    today = date.today()
    samples = [
        ("Income", "180000.00", "Salary", "Demo salary", 2),
        ("Income", "25000.00", "Business", "Demo freelance project", 18),
        ("Expense", "12500.00", "Food", "Demo groceries", 1),
        ("Expense", "4200.00", "Transport", "Demo commute", 4),
        ("Expense", "18500.00", "Bills", "Demo utilities", 8),
        ("Expense", "6500.00", "Entertainment", "Demo weekend outing", 13),
        ("Expense", "10900.00", "Shopping", "Demo home supplies", 30),
        ("Expense", "14000.00", "Food", "Demo monthly groceries", 45),
        ("Income", "15000.00", "Other", "Demo gift", 55),
        ("Expense", "21000.00", "Bills", "Demo rent contribution", 65),
        ("Expense", "7200.00", "Health", "Demo pharmacy", 90),
        ("Expense", "3200.00", "Transport", "Demo train tickets", 120),
    ]
    for kind, amount, category, description, days_ago in samples:
        when = (today - timedelta(days=days_ago)).isoformat()
        if kind == "Income":
            tracker.add_income(amount, category, description, when)
        else:
            tracker.add_expense(amount, category, description, when)


def get_tracker() -> ExpenseTracker:
    """Streamlit session state supplies one SQLite connection per visitor session."""
    if "tracker" not in st.session_state:
        local = os.environ.get("EXPENSE_TRACKER_MODE", "demo").lower() == "local"
        path = Path(__file__).resolve().parent / "expense_tracker.db" if local else ":memory:"
        tracker = ExpenseTracker(path)
        if not local:
            seed_demo(tracker)
        st.session_state.tracker = tracker
        st.session_state.local_mode = local
    return st.session_state.tracker


def display_rows(rows: list[dict]) -> None:
    if not rows:
        st.info("No transactions match this view. Add one to get started.")
        return
    st.dataframe([
        {"Date": row["date"], "Type": row["kind"], "Category": row["category"],
         "Description": row["description"], "Amount": format_pkr(row["amount_paisa"])}
        for row in rows
    ], width="stretch", hide_index=True)


def category_input(tracker: ExpenseTracker, key: str, current: str | None = None) -> str:
    categories = tracker.list_categories()
    options = categories + ["+ New category"]
    index = categories.index(current) if current in categories else 0
    selected = st.selectbox("Category", options, index=index, key=f"{key}_category")
    if selected == "+ New category":
        return st.text_input("New category", key=f"{key}_new_category").strip()
    return selected


def dashboard(tracker: ExpenseTracker) -> None:
    st.markdown('<div class="eyebrow">Overview</div>', unsafe_allow_html=True)
    st.title("Your financial snapshot")
    st.markdown('<p class="subtitle">A clear view of what came in and what went out.</p>', unsafe_allow_html=True)
    totals = tracker.transaction_totals()
    a, b, c = st.columns(3)
    a.metric("Total income", format_pkr(totals["income_paisa"]))
    b.metric("Total expenses", format_pkr(totals["expense_paisa"]))
    c.metric("Net balance", format_pkr(totals["balance_paisa"]))

    rows = tracker.list_transactions()
    expenses = [row for row in rows if row["kind"] == "Expense"]
    monthly: dict[str, int] = defaultdict(int)
    for row in expenses:
        monthly[row["date"][:7]] += row["amount_paisa"]
    left, right = st.columns([1.45, 1], gap="large")
    with left:
        st.subheader("Monthly spending")
        if monthly:
            st.bar_chart([{"Month": month, "Spending (PKR)": amount / 100}
                          for month, amount in sorted(monthly.items())],
                         x="Month", y="Spending (PKR)", color="#176b87", height=310)
        else:
            st.info("Spending will appear here after you add an expense.")
    with right:
        st.subheader("Expenses by category")
        categories = tracker.category_summary()
        if categories:
            st.bar_chart([{"Category": row["category"], "Spending (PKR)": row["total_paisa"] / 100}
                          for row in categories], x="Category", y="Spending (PKR)",
                         color="#e6a45c", height=310)
        else:
            st.info("Category totals will appear here after you add an expense.")

    current = tracker.monthly_summary(date.today().year, date.today().month)
    st.caption(f"This month: {format_pkr(current['total_paisa'])} across {current['count']} expenses")
    st.subheader("Recent transactions")
    display_rows(rows[:8])


def add_transaction(tracker: ExpenseTracker) -> None:
    st.markdown('<div class="eyebrow">Transactions</div>', unsafe_allow_html=True)
    st.title("Add a transaction")
    st.markdown('<p class="subtitle">Record income or spending in Pakistani rupees.</p>', unsafe_allow_html=True)
    with st.form("add_transaction", clear_on_submit=True):
        kind = st.radio("Type", ["Expense", "Income"], horizontal=True)
        left, right = st.columns(2)
        with left:
            amount = st.text_input("Amount (PKR)", placeholder="0.00")
            when = st.date_input("Transaction date", value=date.today())
        with right:
            category = category_input(tracker, "add")
            description = st.text_input("Description", max_chars=200, placeholder="What was this for?")
        submitted = st.form_submit_button("Save transaction", type="primary")
    if submitted:
        try:
            if kind == "Income":
                tracker.add_income(amount, category, description, when.isoformat())
            else:
                tracker.add_expense(amount, category, description, when.isoformat())
            st.success("Transaction saved.")
        except ValueError as error:
            st.warning(str(error))
        except (sqlite3.Error, OSError):
            st.error("Could not save the transaction. Please try again.")


def history(tracker: ExpenseTracker) -> None:
    st.markdown('<div class="eyebrow">Transactions</div>', unsafe_allow_html=True)
    st.title("Transaction history")
    st.markdown('<p class="subtitle">Filter, export, edit, or remove your records.</p>', unsafe_allow_html=True)
    f1, f2, f3 = st.columns([1, 1, 1.4])
    kind = f1.selectbox("Type", ["All", "Expense", "Income"])
    category = f2.selectbox("Category", ["All"] + tracker.list_categories())
    date_range = f3.date_input("Date range", value=(), help="Choose a start and end date")
    start = end = None
    if len(date_range) == 2:
        start, end = (day.isoformat() for day in date_range)
    elif len(date_range) == 1:
        st.info("Choose an end date to apply the date filter.")
    rows = tracker.list_transactions(category=None if category == "All" else category,
                                     start_date=start, end_date=end,
                                     kind=None if kind == "All" else kind)
    st.caption(f"{len(rows)} transaction{'s' if len(rows) != 1 else ''}")
    display_rows(rows)
    st.download_button("Download filtered CSV", data=tracker.transactions_csv(rows).encode("utf-8-sig"),
                       file_name="transactions.csv", mime="text/csv", disabled=not rows)
    if not rows:
        return
    st.divider()
    st.subheader("Manage a transaction")
    labels = {f"{row['date']} · {row['kind']} #{row['id']} · {row['description']}": row for row in rows}
    selected = st.selectbox("Select transaction", list(labels))
    item = labels[selected]
    item_key = f"{item['kind']}_{item['id']}"
    action = st.radio("Action", ["Edit", "Delete"], horizontal=True)
    if action == "Edit":
        with st.form(f"edit_{item_key}"):
            left, right = st.columns(2)
            with left:
                amount = st.text_input("Amount (PKR)", value=f"{Decimal(item['amount_paisa']) / 100:.2f}", key=f"amount_{item_key}")
                when = st.date_input("Transaction date", value=date.fromisoformat(item["date"]), key=f"date_{item_key}")
            with right:
                new_category = category_input(tracker, f"edit_{item_key}", item["category"])
                description = st.text_input("Description", value=item["description"], max_chars=200, key=f"description_{item_key}")
            submitted = st.form_submit_button("Save changes", type="primary")
        if submitted:
            try:
                if item["kind"] == "Income":
                    tracker.edit_income(item["id"], amount, new_category, description, when.isoformat())
                else:
                    tracker.edit_expense(item["id"], amount, new_category, description, when.isoformat())
                st.success("Transaction updated.")
                st.rerun()
            except ValueError as error:
                st.warning(str(error))
            except (sqlite3.Error, OSError):
                st.error("Could not update the transaction. Please try again.")
    else:
        st.warning(f"Delete {item['kind'].lower()} #{item['id']} — {item['description']}?")
        confirm = st.checkbox("I understand this transaction will be deleted", key=f"confirm_{item['kind']}_{item['id']}")
        if st.button("Delete transaction", type="primary", disabled=not confirm):
            try:
                if item["kind"] == "Income":
                    tracker.delete_income(item["id"])
                else:
                    tracker.delete_expense(item["id"])
                st.success("Transaction deleted.")
                st.rerun()
            except (sqlite3.Error, OSError):
                st.error("Could not delete the transaction. Please try again.")


def main() -> None:
    try:
        tracker = get_tracker()
        with st.sidebar:
            st.title("Expense Tracker")
            st.caption("Simple money clarity · PKR")
            page = st.radio("Navigate", ["Dashboard", "Add transaction", "History"], label_visibility="collapsed")
            st.divider()
            if st.session_state.local_mode:
                st.info("Local SQLite mode · records persist on this device.")
            else:
                st.info("Demo mode · fictional data is private to this browser session and may disappear when the session ends.")
                if st.button("Reset demo data"):
                    tracker.close()
                    del st.session_state.tracker
                    st.rerun()
        if page == "Dashboard":
            dashboard(tracker)
        elif page == "Add transaction":
            add_transaction(tracker)
        else:
            history(tracker)
    except (sqlite3.Error, OSError):
        st.error("The database is unavailable. Please reload the app or check the local database configuration.")


if __name__ == "__main__":
    main()
