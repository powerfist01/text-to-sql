"""
db/setup.py
-----------
Creates and populates the SQLite database with:
  - departments table (10 departments)
  - employees table  (200 randomly generated employees)

Also exposes two utility functions used by all src/ approaches:
  - get_schema_info()  → returns human-readable schema string
  - run_sql()          → executes a SQL query and returns a DataFrame
"""

import os
import random
import sqlite3
from datetime import datetime, timedelta

import pandas as pd

# Path to the SQLite database file
DATABASE_PATH = "data/data.db"


def create_database():
    """
    Creates the database and populates it with sample data.
    Skips creation if the database already exists.
    """
    if os.path.exists(DATABASE_PATH):
        print("Database already exists. Skipping creation.")
        return

    print("Creating database...")

    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()

        # --- Create Tables ---
        # departments: simple lookup table
        # employees: main table with a foreign key to departments
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS departments (
                id          INTEGER PRIMARY KEY,
                name        TEXT NOT NULL,
                location    TEXT
            );

            CREATE TABLE IF NOT EXISTS employees (
                id            INTEGER PRIMARY KEY,
                name          TEXT NOT NULL,
                age           INTEGER,
                department_id INTEGER,
                salary        REAL,
                hire_date     DATE,
                FOREIGN KEY (department_id) REFERENCES departments(id)
            );
        """)

        # --- Populate Departments ---
        cursor.executemany(
            "INSERT INTO departments VALUES (?, ?, ?)",
            [
                (1,  "HR",               "New York"),
                (2,  "Engineering",      "San Francisco"),
                (3,  "Marketing",        "Chicago"),
                (4,  "Sales",            "Los Angeles"),
                (5,  "Finance",          "Boston"),
                (6,  "Customer Support", "Dallas"),
                (7,  "Research",         "Seattle"),
                (8,  "Legal",            "Washington D.C."),
                (9,  "Product",          "Austin"),
                (10, "Operations",       "Denver"),
            ],
        )

        # --- Populate Employees (200 random records) ---
        first_names = [
            "John", "Jane", "Bob", "Alice", "Charlie", "Diana",
            "Edward", "Fiona", "George", "Hannah", "Ian", "Julia",
            "Kevin", "Laura", "Michael", "Nora", "Oliver", "Patricia",
            "Quentin", "Rachel", "Steve", "Tina", "Ulysses", "Victoria",
            "William", "Xena", "Yannick", "Zoe",
        ]
        last_names = [
            "Smith", "Johnson", "Williams", "Jones", "Brown", "Davis",
            "Miller", "Wilson", "Moore", "Taylor", "Anderson", "Thomas",
            "Jackson", "White", "Harris", "Martin", "Thompson", "Garcia",
            "Martinez", "Robinson", "Clark", "Rodriguez", "Lewis", "Lee",
            "Walker", "Hall", "Allen", "Young", "King",
        ]

        employees_data = []
        for i in range(1, 201):
            name          = f"{random.choice(first_names)} {random.choice(last_names)}"
            age           = random.randint(22, 65)
            department_id = random.randint(1, 10)
            salary        = round(random.uniform(40000, 200000), 2)
            hire_date     = (
                datetime.now() - timedelta(days=random.randint(0, 3650))
            ).strftime("%Y-%m-%d")
            employees_data.append((i, name, age, department_id, salary, hire_date))

        cursor.executemany(
            "INSERT INTO employees VALUES (?, ?, ?, ?, ?, ?)",
            employees_data
        )

    print("Database created and populated successfully.")


def get_schema_info() -> str:
    """
    Reads the database schema and returns it as a readable string.

    Example output:
        Table: departments
          - id (INTEGER)
          - name (TEXT)
          - location (TEXT)

        Table: employees
          - id (INTEGER)
          - name (TEXT)
          ...
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()

        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        schema_parts = []
        for (table_name,) in tables:
            # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()

            table_info = f"Table: {table_name}\n"
            table_info += "\n".join(f"  - {col[1]} ({col[2]})" for col in columns)
            schema_parts.append(table_info)

    return "\n\n".join(schema_parts)


def run_sql(sql: str) -> pd.DataFrame:
    """
    Executes a SQL query against the database and returns results as a DataFrame.

    Args:
        sql: A valid SQL query string

    Returns:
        pandas DataFrame with query results
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        return pd.read_sql_query(sql, conn)


# --- Quick test when run directly ---
if __name__ == "__main__":
    create_database()

    print("\n--- Schema ---")
    print(get_schema_info())

    print("\n--- Sample: First 5 employees ---")
    print(run_sql("SELECT * FROM employees LIMIT 5").to_string(index=False))

    print("\n--- Sample: All departments ---")
    print(run_sql("SELECT * FROM departments").to_string(index=False))