# Python Expense Tracker

Python Expense Tracker is a reliable, offline, terminal-based application for recording and understanding personal spending in Pakistani Rupees (PKR). Data is saved locally in SQLite and remains available between runs.

## Features

- Add expenses with an amount, category, description, and date
- Built-in categories plus custom categories
- View expenses in date order with a combined total
- Edit or delete records by their unique ID
- Review monthly totals, transaction counts, and spending by category
- View an all-time category summary
- Search descriptions and filter by category or date range
- Export all records to an Excel-compatible CSV file
- Friendly input validation and error messages
- Accurate monetary calculations using integer paisa rather than floating point

## Technologies

- Python 3
- SQLite through Python's built-in `sqlite3` module
- Standard-library `csv`, `decimal`, and `unittest` modules
- No third-party packages, online services, or APIs

## Installation

1. Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/).
2. Open this project folder in Visual Studio Code.
3. Open **Terminal > New Terminal**.
4. Check that Python is available:

   ```powershell
   python --version
   ```

No package installation is required.

## Usage

From the project folder in the VS Code terminal, run:

```powershell
python main.py
```

Choose an option from the numbered menu and follow the prompts. Dates use `YYYY-MM-DD`. Press Enter at the add-expense date prompt to use today's date. A custom category can be created simply by typing its name.

The database is created automatically as `expense_tracker.db` in the project folder. Existing records are retained whenever the program is restarted.

## Testing

Run the complete test suite from the project folder:

```powershell
python -m unittest discover -s tests -v
```

Tests use temporary databases and never access the real application database.

## Project Structure

```text
python-expense-tracker/
├── main.py                       # Interactive terminal menu
├── expense_tracker.py            # Validation and application logic
├── database.py                   # SQLite schema and persistence
├── tests/
│   ├── __init__.py
│   └── test_expense_tracker.py   # Automated tests
├── README.md
└── .gitignore
```

## Future Enhancements

- Optional budgets and overspending alerts
- Recurring expense templates
- Additional report formats
- Database backup and restore commands
- A desktop interface while preserving the offline design
