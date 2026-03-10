"""
Main Database class that combines all mixins.
This is the file you import in your application code.
"""
import sqlite3
from .base import DatabaseBase
from .helpers import CRUDHelpers
from .mixins.farm_mixin import FarmMixin
from .mixins.location_mixin import LocationMixin
from .mixins.market_mixin import MarketMixin
from .mixins.weather_mixin import WeatherMixin
from .schema import TABLES, INDEXES


class Database(DatabaseBase, CRUDHelpers, FarmMixin, LocationMixin,
               MarketMixin, WeatherMixin):
    """
    Main database class combining all functionality.

    Usage:
        from database import Database
        db = Database()
        farms = db.get_all_farms()
    """

    def __init__(self, db_path=None):
        """Initialize database and create schema"""
        super().__init__(db_path)
        self.init_db()
        self.create_indexes()

    def init_db(self):
        """Create all database tables"""
        with self.transaction() as conn:
            cursor = conn.cursor()

            # Create all tables
            for table_name, create_sql in TABLES.items():
                cursor.execute(create_sql)

    def create_indexes(self):
        """Create all database indexes"""
        with self.transaction() as conn:
            cursor = conn.cursor()

            for index_sql in INDEXES:
                try:
                    cursor.execute(index_sql)
                except sqlite3.OperationalError:
                    pass  # Index already exists

    def update_schema(self):
        """
        Legacy method for backward compatibility.
        In the refactored version, schema updates should be handled
        via migrations, but keeping this for existing code.
        """
        # This method is now empty since all columns are in the schema
        # Add migration logic here if needed in the future
        pass


# Export the Database class as the main interface
__all__ = ['Database']