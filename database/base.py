import sqlite3
import os
from contextlib import contextmanager
from config import Config


class DatabaseBase:
    """Base class providing core database connection functionality"""

    def __init__(self, db_path=None):  # This line needs to be indented
        self.db_path = db_path or Config.DATABASE_PATH
        if not self.db_path:
            # Fallback to a default if Config.DATABASE_PATH is also None
            self.db_path = os.path.join(os.getcwd(), 'data', 'farm_database.db')

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def get_connection(self):
        """Get a database connection with Row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def transaction(self):
        """Context manager for database transactions"""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute_query(self, query, params=None):
        """Execute a query and return results as list of dicts"""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            return [dict(row) for row in cursor.fetchall()]

    def execute_one(self, query, params=None):
        """Execute a query and return single result as dict"""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            row = cursor.fetchone()
            return dict(row) if row else None

    def execute_write(self, query, params=None):
        """Execute an INSERT/UPDATE/DELETE and return affected rows or lastrowid"""
        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            return cursor.lastrowid if cursor.lastrowid else cursor.rowcount