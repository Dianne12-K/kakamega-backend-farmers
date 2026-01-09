import sqlite3
import json
import os
from datetime import datetime
from config import Config


class Database:
    def __init__(self, db_path=Config.DATABASE_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_db()
        self.update_schema()
        self.create_indexes()  # Create indexes after schema updates

    # ===== CONNECTION =====

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ===== SCHEMA =====

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        # Sub-Counties Table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS subcounties (
                                                                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                  name TEXT NOT NULL,
                                                                  code TEXT,
                                                                  description TEXT,
                                                                  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                                                  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                       )
                       """)

        # Wards Table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS wards (
                                                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                            name TEXT NOT NULL,
                                                            subcounty_id INTEGER NOT NULL,
                                                            code TEXT,
                                                            population INTEGER DEFAULT 0,
                                                            area_sq_km REAL DEFAULT 0,
                                                            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                                            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                                            FOREIGN KEY (subcounty_id) REFERENCES subcounties(id) ON DELETE CASCADE
                           )
                       """)

        # Farms Table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS farms (
                                                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                            name TEXT NOT NULL,
                                                            crop_type TEXT,
                                                            planting_date TEXT,
                                                            area_ha REAL,
                                                            latitude REAL,
                                                            longitude REAL,
                                                            boundary_geojson TEXT,
                                                            created_at TEXT DEFAULT CURRENT_TIMESTAMP
                       )
                       """)

        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS ndvi_readings (
                                                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                    farm_id INTEGER,
                                                                    date TEXT,
                                                                    ndvi_value REAL,
                                                                    health_score INTEGER,
                                                                    status TEXT,
                                                                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                                                    FOREIGN KEY (farm_id) REFERENCES farms (id)
                           )
                       """)

        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS moisture_readings (
                                                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                        farm_id INTEGER,
                                                                        date TEXT,
                                                                        moisture_percent REAL,
                                                                        status TEXT,
                                                                        days_since_rain INTEGER,
                                                                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                                                        FOREIGN KEY (farm_id) REFERENCES farms (id)
                           )
                       """)

        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS weather_data (
                                                                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                   latitude REAL,
                                                                   longitude REAL,
                                                                   date TEXT,
                                                                   temperature REAL,
                                                                   humidity INTEGER,
                                                                   rain_probability INTEGER,
                                                                   rain_amount REAL,
                                                                   conditions TEXT,
                                                                   created_at TEXT DEFAULT CURRENT_TIMESTAMP
                       )
                       """)

        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS recommendations (
                                                                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                      farm_id INTEGER,
                                                                      priority TEXT,
                                                                      action TEXT,
                                                                      reason TEXT,
                                                                      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                                                      FOREIGN KEY (farm_id) REFERENCES farms (id)
                           )
                       """)

        conn.commit()
        conn.close()

    def update_schema(self):
        """Add new columns to existing tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        new_columns = [
            ("soil_type", "TEXT"),
            ("irrigation", "TEXT"),
            ("fertilizer_used", "TEXT"),
            ("yield_estimate_tons", "REAL"),
            ("status", "TEXT"),
            ("ward_id", "INTEGER"),
        ]

        for col, col_type in new_columns:
            try:
                cursor.execute(f"ALTER TABLE farms ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists

        conn.commit()
        conn.close()

    def create_indexes(self):
        """Create indexes after all columns exist"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_wards_subcounty ON wards(subcounty_id)")
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_farms_ward ON farms(ward_id)")
        except sqlite3.OperationalError:
            pass

        conn.commit()
        conn.close()

    # ===== FARM OPERATIONS =====

    def add_farm(
            self,
            name,
            crop_type,
            planting_date,
            area_ha,
            lat,
            lon,
            boundary_geojson,
            soil_type=None,
            irrigation=None,
            fertilizer_used=None,
            yield_estimate_tons=None,
            status=None,
            ward_id=None,
    ):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
                       INSERT INTO farms (
                           name, crop_type, planting_date, area_ha,
                           latitude, longitude, boundary_geojson,
                           soil_type, irrigation, fertilizer_used,
                           yield_estimate_tons, status, ward_id
                       )
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       """, (
                           name, crop_type, planting_date, area_ha,
                           lat, lon, json.dumps(boundary_geojson),
                           soil_type, irrigation, fertilizer_used,
                           yield_estimate_tons, status, ward_id
                       ))

        farm_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return farm_id

    def get_all_farms(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM farms")
        farms = [dict(row) for row in cursor.fetchall()]
        conn.close()

        for farm in farms:
            if farm.get("boundary_geojson"):
                farm["boundary_geojson"] = json.loads(farm["boundary_geojson"])

        return farms

    def get_farm(self, farm_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM farms WHERE id = ?", (farm_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        farm = dict(row)
        if farm.get("boundary_geojson"):
            farm["boundary_geojson"] = json.loads(farm["boundary_geojson"])

        return farm

    # ===== NDVI =====

    def save_ndvi_reading(self, farm_id, date, ndvi_value, health_score, status):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
                       INSERT INTO ndvi_readings (farm_id, date, ndvi_value, health_score, status)
                       VALUES (?, ?, ?, ?, ?)
                       """, (farm_id, date, ndvi_value, health_score, status))

        conn.commit()
        conn.close()

    def get_latest_ndvi(self, farm_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
                       SELECT * FROM ndvi_readings
                       WHERE farm_id = ?
                       ORDER BY date DESC
                           LIMIT 1
                       """, (farm_id,))

        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_ndvi_history(self, farm_id, days=90):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
                       SELECT date, ndvi_value, health_score, status
                       FROM ndvi_readings
                       WHERE farm_id = ?
                       ORDER BY date DESC
                           LIMIT ?
                       """, (farm_id, days // 5))

        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return list(reversed(rows))

    # ===== MOISTURE =====

    def save_moisture_reading(self, farm_id, date, moisture_percent, status, days_since_rain):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
                       INSERT INTO moisture_readings
                           (farm_id, date, moisture_percent, status, days_since_rain)
                       VALUES (?, ?, ?, ?, ?)
                       """, (farm_id, date, moisture_percent, status, days_since_rain))

        conn.commit()
        conn.close()

    def get_latest_moisture(self, farm_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
                       SELECT * FROM moisture_readings
                       WHERE farm_id = ?
                       ORDER BY date DESC
                           LIMIT 1
                       """, (farm_id,))

        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # ===== WEATHER =====

    def save_weather_forecast(self, lat, lon, forecast_data):
        conn = self.get_connection()
        cursor = conn.cursor()

        for day in forecast_data:
            cursor.execute("""
                           INSERT INTO weather_data
                           (latitude, longitude, date, temperature, humidity,
                            rain_probability, rain_amount, conditions)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                           """, (
                               lat, lon, day["date"], day["temp"], day["humidity"],
                               day["rain_prob"], day["rain_mm"], day["conditions"]
                           ))

        conn.commit()
        conn.close()

    def get_weather_forecast(self, lat, lon, days=7):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
                       SELECT * FROM weather_data
                       WHERE latitude = ? AND longitude = ?
                       ORDER BY date ASC
                           LIMIT ?
                       """, (lat, lon, days))

        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    # ===== RECOMMENDATIONS =====

    def save_recommendation(self, farm_id, priority, action, reason):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM recommendations WHERE farm_id = ?", (farm_id,))
        cursor.execute("""
                       INSERT INTO recommendations (farm_id, priority, action, reason)
                       VALUES (?, ?, ?, ?)
                       """, (farm_id, priority, action, reason))

        conn.commit()
        conn.close()

    def get_recommendation(self, farm_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
                       SELECT * FROM recommendations
                       WHERE farm_id = ?
                       ORDER BY created_at DESC
                           LIMIT 1
                       """, (farm_id,))

        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # ==========================================
    # SUB-COUNTY METHODS
    # ==========================================

    def get_all_subcounties(self):
        """Get all sub-counties"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM subcounties ORDER BY name")
        subcounties = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return subcounties

    def get_subcounty(self, subcounty_id):
        """Get single sub-county by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM subcounties WHERE id = ?", (subcounty_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def add_subcounty(self, name, code='', description=''):
        """Add new sub-county"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO subcounties (name, code, description)
                       VALUES (?, ?, ?)
                       """, (name, code, description))
        subcounty_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return subcounty_id

    def update_subcounty(self, subcounty_id, name=None, code=None, description=None):
        """Update sub-county"""
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if code is not None:
            updates.append("code = ?")
            params.append(code)
        if description is not None:
            updates.append("description = ?")
            params.append(description)

        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(subcounty_id)

        conn = self.get_connection()
        cursor = conn.cursor()
        query = f"UPDATE subcounties SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, tuple(params))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        return rows_affected > 0

    def delete_subcounty(self, subcounty_id):
        """Delete sub-county"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM subcounties WHERE id = ?", (subcounty_id,))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        return rows_affected > 0

    def get_ward_count_by_subcounty(self, subcounty_id):
        """Get count of wards in a sub-county"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM wards WHERE subcounty_id = ?", (subcounty_id,))
        result = cursor.fetchone()
        conn.close()
        return result['count'] if result else 0

    # ==========================================
    # WARD METHODS
    # ==========================================

    def get_all_wards(self):
        """Get all wards"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wards ORDER BY name")
        wards = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return wards

    def get_ward(self, ward_id):
        """Get single ward by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wards WHERE id = ?", (ward_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_wards_by_subcounty(self, subcounty_id):
        """Get all wards in a sub-county"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM wards WHERE subcounty_id = ? ORDER BY name", (subcounty_id,))
        wards = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return wards

    def add_ward(self, name, subcounty_id, code='', population=0, area_sq_km=0):
        """Add new ward"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO wards (name, subcounty_id, code, population, area_sq_km)
                       VALUES (?, ?, ?, ?, ?)
                       """, (name, subcounty_id, code, population, area_sq_km))
        ward_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return ward_id

    def update_ward(self, ward_id, name=None, subcounty_id=None, code=None,
                    population=None, area_sq_km=None):
        """Update ward"""
        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if subcounty_id is not None:
            updates.append("subcounty_id = ?")
            params.append(subcounty_id)
        if code is not None:
            updates.append("code = ?")
            params.append(code)
        if population is not None:
            updates.append("population = ?")
            params.append(population)
        if area_sq_km is not None:
            updates.append("area_sq_km = ?")
            params.append(area_sq_km)

        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(ward_id)

        conn = self.get_connection()
        cursor = conn.cursor()
        query = f"UPDATE wards SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, tuple(params))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        return rows_affected > 0

    def delete_ward(self, ward_id):
        """Delete ward"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM wards WHERE id = ?", (ward_id,))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        return rows_affected > 0

    def get_farms_by_ward(self, ward_id):
        """Get all farms in a ward"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM farms WHERE ward_id = ? ORDER BY name", (ward_id,))
        farms = [dict(row) for row in cursor.fetchall()]
        conn.close()

        for farm in farms:
            if farm.get("boundary_geojson"):
                farm["boundary_geojson"] = json.loads(farm["boundary_geojson"])

        return farms