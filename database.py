"""SQLite persistence for the Python Expense Tracker."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable


DEFAULT_CATEGORIES = (
    "Food",
    "Transport",
    "Bills",
    "Shopping",
    "Health",
    "Education",
    "Entertainment",
    "Business",
    "Other",
)


class Database:
    """Small database wrapper that owns the schema and SQL operations."""

    def __init__(self, database_path: str | Path = "expense_tracker.db") -> None:
        self.path = str(database_path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_tables()

    def _create_tables(self) -> None:
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL COLLATE NOCASE UNIQUE
                )
                """
            )
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount_paisa INTEGER NOT NULL CHECK (amount_paisa > 0),
                    category_id INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    expense_date TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES categories(id)
                )
                """
            )
            self.connection.executemany(
                "INSERT OR IGNORE INTO categories (name) VALUES (?)",
                ((name,) for name in DEFAULT_CATEGORIES),
            )

    def execute(
        self, query: str, parameters: Iterable[Any] = ()
    ) -> sqlite3.Cursor:
        with self.connection:
            return self.connection.execute(query, tuple(parameters))

    def fetchone(
        self, query: str, parameters: Iterable[Any] = ()
    ) -> sqlite3.Row | None:
        return self.connection.execute(query, tuple(parameters)).fetchone()

    def fetchall(
        self, query: str, parameters: Iterable[Any] = ()
    ) -> list[sqlite3.Row]:
        return self.connection.execute(query, tuple(parameters)).fetchall()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
