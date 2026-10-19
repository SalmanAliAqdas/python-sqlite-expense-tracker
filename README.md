# Python Expense Tracker

A Python expense tracker with a Streamlit dashboard and an independent terminal application. Track income and expenses in Pakistani rupees (PKR), review spending, and export records. Monetary amounts are stored as integer paisa for accurate totals.

**Live demo:** [Add your Streamlit Community Cloud URL here](https://share.streamlit.io/)

## Features

- Dashboard with income, expenses, balance, monthly spending, category breakdown, and recent transactions
- Interactive spending charts and a responsive sidebar interface
- Add, edit, and delete income and expenses with dates, categories, and descriptions
- Filter transaction history by date, category, and type; download filtered CSV data
- Existing terminal application remains available for expense management and reports
- Isolated fictional demo data for each web visitor by default

## Technology stack

Python 3.10+, Streamlit, and SQLite through Python's standard `sqlite3` module. The application uses Python's `decimal`, `csv`, and `unittest` modules. Streamlit provides the charts; no separate charting package is required.

## Installation

```bash
python -m venv .venv
python -m pip install -r requirements.txt
```

Activate the virtual environment using the command appropriate for your shell before installing if preferred. The terminal application itself needs only Python's standard library.

## Run locally

Start the web app in demo mode:

```bash
streamlit run streamlit_app.py
```

Demo mode uses a separate in-memory SQLite database for each Streamlit session. It starts with fictional examples and never opens `expense_tracker.db`. Changes may disappear when the session ends or the app restarts. Do not enter real financial information in a public demo.

For private local use with persistent SQLite storage, set `EXPENSE_TRACKER_MODE=local` before starting Streamlit. In PowerShell:

```powershell
$env:EXPENSE_TRACKER_MODE = "local"
streamlit run streamlit_app.py
```

Local mode uses `expense_tracker.db` in the repository directory. The schema adds an `incomes` table while retaining existing expense tables and records. Keep local mode private: it is a single shared database and has no user authentication.

The existing terminal application still runs independently:

```bash
python main.py
```

The terminal interface continues to manage expenses in the same local SQLite database.

## Deploy to Streamlit Community Cloud

1. Review the repository and confirm that no private SQLite files or exports are tracked in Git. The `.gitignore` excludes local databases and generated exports.
2. Publish the source repository to GitHub.
3. In Streamlit Community Cloud, create an app from that repository and select **`streamlit_app.py`** as the main file.
4. Leave `EXPENSE_TRACKER_MODE` unset so the public app starts in demo mode.
5. Add the deployed URL to the live demo link above.

Community Cloud's local filesystem is not guaranteed to persist across restarts or redeployments. The public demo therefore uses session-isolated in-memory SQLite storage. It does not offer durable financial storage, accounts, or cross-device sync. Do not deploy a shared writable SQLite file containing real records.

## Screenshots

- Dashboard screenshot: _add after publishing_
- Transaction history screenshot: _add after publishing_

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests use temporary files and in-memory databases. They do not access the local application database.

## Project files

| File | Purpose |
| --- | --- |
| `streamlit_app.py` | Web entry point and session-isolated demo |
| `main.py` | Existing terminal interface |
| `expense_tracker.py` | Validation, transaction operations, reports, and CSV export |
| `database.py` | SQLite schema and connection wrapper |
| `tests/` | Automated tests |
