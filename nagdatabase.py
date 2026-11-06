"""
database.py - everything related to storing data in SQLite.

SQLite is a tiny database stored in a single file (finance.db).
Python includes it by default, so there is nothing extra to install.
"""

import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

# The database file sits next to this script.
DB_PATH = Path(__file__).parent / "finance.db"

INCOME_CATEGORIES = ["Salary", "Freelance", "Other income"]
EXPENSE_CATEGORIES = ["Food", "Rent", "Travel", "Shopping", "Bills", "Education", "Other"]

COLUMNS = ["id", "date", "description", "category", "type", "amount"]


@contextmanager
def get_connection():
    """Open a connection, save (commit) changes, and always close it."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create the tables the first time the app runs."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT NOT NULL,
                description TEXT NOT NULL,
                category    TEXT NOT NULL,
                type        TEXT NOT NULL CHECK (type IN ('Income', 'Expense')),
                amount      REAL NOT NULL CHECK (amount > 0)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS budgets (
                month  TEXT PRIMARY KEY,          -- e.g. '2026-11'
                amount REAL NOT NULL CHECK (amount >= 0)
            )
            """
        )


# ---------- Transactions ----------

def add_transaction(t_date, description, category, t_type, amount):
    """Insert one transaction. '?' placeholders protect against SQL injection."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO transactions (date, description, category, type, amount) "
            "VALUES (?, ?, ?, ?, ?)",
            (t_date.isoformat(), description.strip(), category, t_type, float(amount)),
        )


def delete_transaction(transaction_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM transactions WHERE id = ?", (int(transaction_id),))


def get_transactions():
    """Return all transactions as a Pandas DataFrame (with a 'month' column)."""
    with get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT id, date, description, category, type, amount FROM transactions",
            conn,
        )
    if df.empty:
        df = pd.DataFrame(columns=COLUMNS)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)
    df["month"] = df["date"].dt.strftime("%Y-%m")
    return df.sort_values(["date", "id"], ascending=False).reset_index(drop=True)


def clear_all_data():
    with get_connection() as conn:
        conn.execute("DELETE FROM transactions")
        conn.execute("DELETE FROM budgets")


# ---------- Budgets ----------

def set_budget(month, amount):
    """Insert or update the budget for a month like '2026-11'."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO budgets (month, amount) VALUES (?, ?) "
            "ON CONFLICT(month) DO UPDATE SET amount = excluded.amount",
            (month, float(amount)),
        )


def get_budget(month):
    """Return the budget for a month, or 0.0 if none is set."""
    with get_connection() as conn:
        row = conn.execute("SELECT amount FROM budgets WHERE month = ?", (month,)).fetchone()
    return float(row[0]) if row else 0.0


# ---------- Helpers & sample data ----------

def month_start(offset=0):
    """First day of the month, `offset` months before the current one."""
    today = date.today()
    year, month = today.year, today.month - offset
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def load_sample_data():
    """Add three months of realistic demo transactions (never in the future)."""
    rng = np.random.RandomState(42)
    today = date.today()
    rows = []

    def add(start, day, desc, cat, typ, amt, last_day):
        d = start.replace(day=min(day, last_day))
        rows.append((d.isoformat(), desc, cat, typ, round(float(amt), 2)))

    for offset in range(3):
        start = month_start(offset)
        last_day = today.day if offset == 0 else 28
        add(start, 1, "Monthly salary", "Salary", "Income", 50000, last_day)
        add(start, 3, "House rent", "Rent", "Expense", 15000, last_day)
        add(start, 5, "Electricity & internet", "Bills", "Expense", rng.randint(1500, 2500), last_day)
        add(start, 8, "Online course", "Education", "Expense", rng.randint(500, 3000), last_day)
        add(start, 12, "Weekend trip", "Travel", "Expense", rng.randint(800, 4000), last_day)
        add(start, 15, "Clothes", "Shopping", "Expense", rng.randint(1000, 5000), last_day)
        add(start, 18, "Logo design project", "Freelance", "Income", rng.randint(4000, 12000), last_day)
        for day in (2, 9, 16, 23):
            add(start, day, "Groceries / eating out", "Food", "Expense", rng.randint(400, 1500), last_day)

    with get_connection() as conn:
        conn.executemany(
            "INSERT INTO transactions (date, description, category, type, amount) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
