"""Session-isolated Streamlit interface for the existing expense tracker."""

from __future__ import annotations

import os
import sqlite3
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import streamlit as st

from dashboard_ui import (
    category_chart, comparison_chart, monthly_data, period_markup,
    spending_chart, summary_cards,
)
from expense_tracker import ExpenseTracker, format_pkr


ROOT = Path(__file__).resolve().parent


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
        # Streamlit may hand a session to another script thread on rerun. The
        # database wrapper serializes access; the connection remains session-only.
        tracker = ExpenseTracker(path, check_same_thread=False)
        if not local:
            seed_demo(tracker)
        st.session_state.tracker = tracker
        st.session_state.local_mode = local
    return st.session_state.tracker


def navigate(page: str) -> None:
    st.session_state.page = page


def page_header(title: str, subtitle: str, rows: list[dict], section: str, period_label: str = "All time") -> None:
    left, right = st.columns([3, 1.2], vertical_alignment="center", gap="medium")
    with left:
        st.markdown(f'<div class="page-eyebrow">Workspace / {section}</div>', unsafe_allow_html=True)
        st.title(title)
        st.markdown(f'<div class="page-subtitle">{subtitle}</div>', unsafe_allow_html=True)
    with right:
        st.markdown(period_markup(rows, period_label), unsafe_allow_html=True)
    st.space("small")


def empty_state(title: str, message: str) -> None:
    # Only application-owned strings are passed here.
    st.markdown(f'<div class="empty-state"><span class="empty-icon" aria-hidden="true">↗</span>'
                f'<strong>{title}</strong><p>{message}</p></div>', unsafe_allow_html=True)


def display_rows(rows: list[dict], *, compact: bool = False) -> None:
    if not rows:
        empty_state("A fresh start", "Add a transaction, or adjust your filters, to see your activity here.")
        return
    st.dataframe([
        {"Date": date.fromisoformat(row["date"]), "Type": row["kind"], "Category": row["category"],
         "Description": row["description"], "Amount": row["amount_paisa"] / 100}
        for row in rows
    ], column_config={
        "Date": st.column_config.DateColumn("Date", format="DD MMM YYYY", width="small"),
        "Type": st.column_config.TextColumn("Type", width="small"),
        "Category": st.column_config.TextColumn("Category", width="small"),
        "Description": st.column_config.TextColumn("Description", width="medium"),
        "Amount": st.column_config.NumberColumn("Amount (PKR)", format="localized", width="small"),
    }, width="stretch", hide_index=True, row_height=43,
        height="content" if compact or len(rows) <= 8 else 420)


def category_input(tracker: ExpenseTracker, key: str, current: str | None = None) -> str:
    categories = tracker.list_categories()
    index = categories.index(current) if current in categories else 0
    # Native new-option support also works inside a form, without conditional reruns.
    return st.selectbox("Category", categories, index=index, key=f"{key}_category",
                        accept_new_options=True, help="Choose a category or type a new one.") or ""


def spending_panel(months: list[dict], key: str) -> None:
    with st.container(border=True, key=key):
        st.subheader("Monthly spending")
        st.markdown('<div class="chart-note">How your expenses add up over time</div>', unsafe_allow_html=True)
        if any(month["Expense"] for month in months):
            st.altair_chart(spending_chart(months), width="stretch", theme=None,
                            alt="Monthly expenses in Pakistani rupees. Hover over a point for the exact amount.")
        else:
            empty_state("Your spending story starts here", "Add an expense to see your monthly pattern.")


def categories_panel(categories: list[dict], key: str) -> None:
    with st.container(border=True, key=key):
        st.subheader("Expenses by category")
        st.markdown('<div class="chart-note">Where your money goes</div>', unsafe_allow_html=True)
        if categories:
            # A bounded chart prevents custom category lists stretching the dashboard.
            shown = categories[:6]
            if len(categories) > 6:
                shown = shown + [{"category": "Remaining categories", "total_paisa":
                                  sum(row["total_paisa"] for row in categories[6:])}]
                st.caption("Top six categories; the rest are grouped.")
            st.altair_chart(category_chart(shown), width="stretch", theme=None,
                            alt="Horizontal bars comparing category spending. Hover for category names and amounts.")
        else:
            empty_state("Make sense of your spending", "Your expense categories will appear here.")


def dashboard(tracker: ExpenseTracker) -> None:
    rows = tracker.list_transactions()
    page_header("Expense Tracker", "Keep your money in focus. A little clarity goes a long way.", rows, "Overview")
    title, action = st.columns([3, 1], vertical_alignment="center")
    title.subheader("Financial overview")
    action.button("Add transaction", icon=":material/add:", type="primary", width="stretch",
                  key="dashboard_add", on_click=navigate, args=("Add Transaction",))
    st.markdown(summary_cards(tracker.transaction_totals()), unsafe_allow_html=True)
    st.space("small")
    left, right = st.columns([1.5, 1], gap="medium")
    with left:
        spending_panel(monthly_data(rows), "chart_spending")
    with right:
        categories_panel(tracker.category_summary(), "chart_categories")
    current = tracker.monthly_summary(date.today().year, date.today().month)
    st.caption(f"This month · {format_pkr(current['total_paisa'])} spent · {current['count']} expenses")
    with st.container(border=True, key="recent_transactions"):
        left, right = st.columns([4, 1], vertical_alignment="center")
        left.subheader("Recent transactions")
        right.button("View all", icon=":material/arrow_forward:", width="stretch",
                     key="view_all", on_click=navigate, args=("Transactions",))
        display_rows(rows[:6], compact=True)


def add_transaction(tracker: ExpenseTracker) -> None:
    page_header("Add transaction", "A small update today. A clearer picture tomorrow.",
                tracker.list_transactions(), "Transactions")
    with st.container(border=True, key="add_panel"):
        st.subheader("Transaction details")
        kind = st.segmented_control("Transaction type", ["Expense", "Income"], default="Expense",
                                    required=True, key="add_kind", width="stretch",
                                    format_func=lambda value: f"{'↗' if value == 'Expense' else '↙'} {value}")
        st.caption("Record money you spent." if kind == "Expense" else "Record money you received.")
        revision = st.session_state.get("add_revision", 0)
        field_key = f"add_{revision}"
        with st.form(f"add_transaction_{revision}", border=False):
            left, right = st.columns(2, gap="medium")
            with left:
                amount = st.text_input("Amount (PKR)", placeholder="0.00", key=f"{field_key}_amount",
                                       max_chars=24, help="Enter an amount such as 1250.50, without currency symbols or commas.")
            with right:
                when = st.date_input("Transaction date", value=date.today(), key=f"{field_key}_date")
            category = category_input(tracker, field_key)
            description = st.text_area("Description", max_chars=200, height=90,
                                        placeholder="What was this transaction for?", key=f"{field_key}_description")
            st.caption("Amounts are recorded in PKR, with precision to two decimal places.")
            submitted = st.form_submit_button("Save transaction", type="primary", icon=":material/check:", width="stretch")
        if submitted:
            try:
                if kind == "Income":
                    tracker.add_income(amount, category, description, when.isoformat())
                else:
                    tracker.add_expense(amount, category, description, when.isoformat())
                st.session_state.add_revision = revision + 1
                st.session_state.flash = "Transaction saved. Your overview is up to date."
                st.rerun()
            except ValueError as error:
                st.warning(str(error), icon=":material/info:")
            except (sqlite3.Error, OSError):
                st.error("We couldn't save that transaction. Your entries are still here; please try again.")


def edit_transaction(tracker: ExpenseTracker, item: dict) -> None:
    revision = st.session_state.get("edit_revision", 0)
    item_key = f"{item['kind']}_{item['id']}_{revision}"
    edit_tab, delete_tab = st.tabs(["Edit details", "Delete transaction"])
    with edit_tab:
        with st.form(f"edit_{item_key}", border=False):
            left, right = st.columns(2, gap="medium")
            with left:
                amount = st.text_input("Amount (PKR)", value=f"{Decimal(item['amount_paisa']) / 100:.2f}",
                                       key=f"amount_{item_key}", max_chars=24)
            with right:
                when = st.date_input("Transaction date", value=date.fromisoformat(item["date"]), key=f"date_{item_key}")
            new_category = category_input(tracker, f"edit_{item_key}", item["category"])
            description = st.text_area("Description", value=item["description"], max_chars=200,
                                        height=90, key=f"description_{item_key}")
            submitted = st.form_submit_button("Save changes", type="primary", icon=":material/check:")
        if submitted:
            try:
                if item["kind"] == "Income":
                    tracker.edit_income(item["id"], amount, new_category, description, when.isoformat())
                else:
                    tracker.edit_expense(item["id"], amount, new_category, description, when.isoformat())
                st.session_state.edit_revision = revision + 1
                st.session_state.flash = "Transaction updated. Your changes have been saved."
                st.rerun()
            except ValueError as error:
                st.warning(str(error), icon=":material/info:")
            except (sqlite3.Error, OSError):
                st.error("We couldn't update that transaction. Please try again.")
    with delete_tab:
        st.warning(f"Delete {item['kind'].lower()} #{item['id']}: {item['description']} ({format_pkr(item['amount_paisa'])})?")
        confirm = st.checkbox("I confirm I want to delete this transaction.", key=f"confirm_{item_key}")
        with st.container(key="delete_control"):
            delete = st.button("Delete transaction", icon=":material/delete:", disabled=not confirm, key="delete_transaction")
        if delete:
            try:
                if item["kind"] == "Income":
                    tracker.delete_income(item["id"])
                else:
                    tracker.delete_expense(item["id"])
                st.session_state.edit_revision = revision + 1
                st.session_state.flash = "Transaction deleted."
                st.rerun()
            except (sqlite3.Error, OSError):
                st.error("We couldn't delete that transaction. Please try again.")


def history(tracker: ExpenseTracker) -> None:
    page_header("Transactions", "Every detail, in one place. Filter, review, and make it yours.",
                tracker.list_transactions(), "Transactions")
    with st.container(border=True, key="filters"):
        f1, f2, f3 = st.columns([1, 1, 1.4], gap="medium")
        kind = f1.selectbox("Type", ["All types", "Expense", "Income"], key="filter_kind")
        category = f2.selectbox("Category", ["All categories"] + tracker.list_categories(), key="filter_category")
        date_range = f3.date_input("Date range", value=(), key="filter_dates", help="Choose a start and end date. Clear to show all dates.")
    start = end = None
    if len(date_range) == 2:
        start, end = (day.isoformat() for day in date_range)
    elif len(date_range) == 1:
        st.info("Choose an end date to finish your date filter.")
        return
    rows = tracker.list_transactions(category=None if category == "All categories" else category,
                                     start_date=start, end_date=end,
                                     kind=None if kind == "All types" else kind)
    with st.container(border=True, key="transaction_table"):
        left, right = st.columns([3, 1], vertical_alignment="center")
        left.subheader("Transaction history")
        right.download_button("Export CSV", data=tracker.transactions_csv(rows).encode("utf-8-sig"),
                              file_name="transactions.csv", mime="text/csv", disabled=not rows,
                              icon=":material/download:", width="stretch", key="export_transactions")
        st.caption(f"{len(rows)} transaction{'s' if len(rows) != 1 else ''} · Export includes the current filters")
        display_rows(rows)
    if rows:
        with st.expander("Edit or delete a transaction", icon=":material/edit_note:"):
            records = {f"{row['kind']}:{row['id']}": row for row in rows}
            selected = st.selectbox("Select transaction", list(records), key="selected_transaction",
                                    format_func=lambda key: f"{records[key]['date']} · {records[key]['kind']} · {records[key]['description']} · {format_pkr(records[key]['amount_paisa'])}")
            edit_transaction(tracker, records[selected])


def analytics(tracker: ExpenseTracker) -> None:
    all_rows = tracker.list_transactions()
    months = sorted({row["date"][:7] for row in all_rows}, reverse=True)
    period = st.session_state.get("analytics_period", "All time")
    if period not in ["All time"] + months:
        period = "All time"
        st.session_state.analytics_period = period
    if period == "All time":
        rows = all_rows
        categories = tracker.category_summary()
    else:
        year, month = map(int, period.split("-"))
        rows = tracker.list_transactions(start_date=f"{period}-01", end_date=f"{period}-{monthrange(year, month)[1]}")
        categories = [{"category": category, "total_paisa": total} for category, total in
                      tracker.monthly_summary(year, month)["by_category"].items()]
    period_label = period if period == "All time" else date.fromisoformat(period + "-01").strftime("%B %Y")
    page_header("Analytics", "Understand the patterns behind your everyday money decisions.", rows, "Analytics", period_label)
    st.selectbox("Analysis period", ["All time"] + months, key="analytics_period",
                 format_func=lambda value: value if value == "All time" else date.fromisoformat(value + "-01").strftime("%B %Y"))
    monthly = monthly_data(rows)
    with st.container(border=True, key="analytics_comparison"):
        st.subheader("Income vs expenses")
        st.markdown('<div class="chart-note">Monthly cash flow · exact amounts on hover</div>', unsafe_allow_html=True)
        if monthly:
            st.altair_chart(comparison_chart(monthly), width="stretch", theme=None,
                            alt="Grouped bars showing monthly income in green and expenses in coral.")
        else:
            empty_state("Your cash flow, made clear", "Add income or expenses to start exploring.")
    left, right = st.columns([1.5, 1], gap="medium")
    with left:
        spending_panel(monthly, "analytics_spending")
    with right:
        categories_panel(categories, "analytics_categories")
    with st.container(border=True, key="monthly_table"):
        st.subheader("Monthly breakdown")
        if monthly:
            st.dataframe([{"Month": row["Label"], "Income": row["Income"] / 100,
                           "Expenses": row["Expense"] / 100,
                           "Net balance": (row["Income"] - row["Expense"]) / 100}
                          for row in reversed(monthly)], hide_index=True, width="stretch",
                         column_config={key: st.column_config.NumberColumn(f"{key} (PKR)", format="localized")
                                        for key in ("Income", "Expenses", "Net balance")})
        else:
            st.caption("Your monthly totals will appear after your first transaction.")


def settings(tracker: ExpenseTracker) -> None:
    page_header("Settings", "Your workspace, your preferences, and your demo controls.",
                tracker.list_transactions(), "Settings")
    local = st.session_state.local_mode
    with st.container(border=True, key="settings_info"):
        st.subheader("Workspace details")
        st.markdown('<div class="setting-row"><span>Currency</span><strong>PKR · Pakistani rupee</strong></div>'
                    f'<div class="setting-row"><span>Workspace</span><strong>{"Private local" if local else "Personal demo session"}</strong></div>'
                    f'<div class="setting-row"><span>Storage</span><strong>{"Local SQLite" if local else "Session memory"}</strong></div>',
                    unsafe_allow_html=True)
        if local:
            st.caption("Records persist in your local database. Keep this mode restricted to private use.")
        else:
            st.caption("Fictional demo data is isolated to this browser session. Changes may disappear when your session ends or the app restarts.")
    if not local:
        with st.container(border=True, key="demo_controls"):
            st.subheader("Demo controls")
            st.write("Start fresh with the original fictional transactions. This resets only your current demo session.")
            confirm = st.checkbox("I confirm I want to reset my demo data.", key="confirm_demo_reset")
            if st.button("Reset demo data", icon=":material/restart_alt:", disabled=not confirm, key="reset_demo"):
                tracker.close()
                del st.session_state.tracker
                # Drop widget drafts and confirmations after replacing this session's data.
                for key in list(st.session_state):
                    if key not in ("page", "local_mode"):
                        del st.session_state[key]
                st.session_state.flash = "Demo data reset. You're ready for a fresh start."
                st.rerun()


def sidebar() -> str:
    page = st.session_state.get("page", "Dashboard")
    navigation = [("Dashboard", "dashboard", "space_dashboard"),
                  ("Add Transaction", "add", "add_circle"),
                  ("Transactions", "transactions", "receipt_long"),
                  ("Analytics", "analytics", "bar_chart"),
                  ("Settings", "settings", "tune")]
    with st.sidebar, st.container(key="sidebar_content"):
        st.markdown('<div class="brand"><span class="brand-icon" aria-hidden="true">'
                    '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">'
                    '<rect x="3" y="5" width="18" height="15" rx="3"/><path d="M3 9h18M16 13h5"/>'
                    '<circle cx="16" cy="15" r=".7" fill="currentColor"/></svg></span>'
                    '<div><div class="brand-name">Expense Tracker</div><div class="brand-caption">Make room for clarity.</div></div></div>'
                    '<div class="nav-label">WORKSPACE</div>', unsafe_allow_html=True)
        with st.container(key="navigation"):
            for label, key, icon in navigation:
                with st.container(key="nav_active" if label == page else f"nav_item_{key}"):
                    st.button(label, key=f"nav_{key}", icon=f":material/{icon}:", width="stretch",
                              on_click=navigate, args=(label,))
        local = st.session_state.local_mode
        st.markdown('<div class="sidebar-session"><div class="session-title"><span class="session-dot"></span>'
                    f'{"Local workspace" if local else "Demo workspace"}</div>'
                    f'{"Your records are saved on this device." if local else "Fictional data. Private to your session. Changes may disappear when the session ends."}'
                    '</div><div class="sidebar-footnote">PKR currency · Simple money clarity</div>', unsafe_allow_html=True)
    return st.session_state.get("page", "Dashboard")


def main() -> None:
    st.set_page_config(page_title="Expense Tracker", page_icon="💸",
                       layout="wide", initial_sidebar_state="auto")
    st.markdown(f"<style>{(ROOT / 'assets' / 'styles.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    try:
        tracker = get_tracker()
        page = sidebar()
        with st.container(key="workspace"):
            if message := st.session_state.pop("flash", None):
                st.success(message, icon=":material/check_circle:")
            views = {"Dashboard": dashboard, "Add Transaction": add_transaction,
                     "Transactions": history, "Analytics": analytics, "Settings": settings}
            views.get(page, dashboard)(tracker)
    except (sqlite3.Error, OSError):
        st.error("The database is unavailable. Please reload the app or check the local database configuration.")


if __name__ == "__main__":
    main()
