import sqlite3
import json
import os
from datetime import datetime, date
from config import Config


class Database:
    def __init__(self, db_path=Config.DATABASE_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_db()
        self.update_schema()
        self.create_indexes()

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

        # ===== NEW MARKET DATA TABLES =====

        # Markets Table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS markets (
                                                              id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                              name TEXT NOT NULL,
                                                              location TEXT,
                                                              contact_phone TEXT,
                                                              contact_person TEXT,
                                                              operating_days TEXT,
                                                              payment_terms TEXT,
                                                              is_active INTEGER DEFAULT 1,
                                                              created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                                              updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                       )
                       """)

        # Market Prices Table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS market_prices (
                                                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                    market_id INTEGER NOT NULL,
                                                                    crop_type TEXT NOT NULL,
                                                                    price REAL NOT NULL,
                                                                    unit TEXT DEFAULT 'per 90kg bag',
                                                                    grade TEXT,
                                                                    date_recorded TEXT,
                                                                    is_current INTEGER DEFAULT 1,
                                                                    notes TEXT,
                                                                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                                                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                                                    FOREIGN KEY (market_id) REFERENCES markets(id) ON DELETE CASCADE
                           )
                       """)

        # Collection Centers Table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS collection_centers (
                                                                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                         name TEXT NOT NULL,
                                                                         location TEXT,
                                                                         latitude REAL,
                                                                         longitude REAL,
                                                                         crops_accepted TEXT,
                                                                         contact_phone TEXT,
                                                                         contact_person TEXT,
                                                                         operating_days TEXT,
                                                                         operating_hours TEXT,
                                                                         storage_capacity TEXT,
                                                                         payment_terms TEXT,
                                                                         minimum_quantity TEXT,
                                                                         quality_requirements TEXT,
                                                                         is_active INTEGER DEFAULT 1,
                                                                         created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                                                         updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_wards_subcounty ON wards(subcounty_id)",
            "CREATE INDEX IF NOT EXISTS idx_farms_ward ON farms(ward_id)",
            "CREATE INDEX IF NOT EXISTS idx_market_prices_market ON market_prices(market_id)",
            "CREATE INDEX IF NOT EXISTS idx_market_prices_crop ON market_prices(crop_type)",
            "CREATE INDEX IF NOT EXISTS idx_market_prices_current ON market_prices(is_current)",
        ]

        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
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

    # ==========================================
    # MARKET CRUD OPERATIONS
    # ==========================================

    def add_market(self, name, location=None, contact_phone=None, contact_person=None,
                   operating_days=None, payment_terms=None):
        """Add new market"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO markets (name, location, contact_phone, contact_person,
                                            operating_days, payment_terms)
                       VALUES (?, ?, ?, ?, ?, ?)
                       """, (name, location, contact_phone, contact_person, operating_days, payment_terms))
        market_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return market_id

    def get_all_markets(self, active_only=True):
        """Get all markets"""
        conn = self.get_connection()
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM markets WHERE is_active = 1 ORDER BY name")
        else:
            cursor.execute("SELECT * FROM markets ORDER BY name")
        markets = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return markets

    def get_market(self, market_id):
        """Get single market by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM markets WHERE id = ?", (market_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_market(self, market_id, **kwargs):
        """Update market with any fields"""
        updates = []
        params = []

        for key, value in kwargs.items():
            if value is not None:
                updates.append(f"{key} = ?")
                params.append(value)

        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(market_id)

        conn = self.get_connection()
        cursor = conn.cursor()
        query = f"UPDATE markets SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, tuple(params))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        return rows_affected > 0

    def delete_market(self, market_id):
        """Soft delete market (set is_active = 0)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       UPDATE markets SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?
                       """, (market_id,))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        return rows_affected > 0

    # ==========================================
    # MARKET PRICE CRUD OPERATIONS
    # ==========================================

    def add_market_price(self, market_id, crop_type, price, unit='per 90kg bag',
                         grade=None, date_recorded=None, notes=None):
        """Add new market price"""
        if date_recorded is None:
            date_recorded = date.today().isoformat()

        conn = self.get_connection()
        cursor = conn.cursor()

        # Mark previous prices for this market/crop as not current
        cursor.execute("""
                       UPDATE market_prices SET is_current = 0
                       WHERE market_id = ? AND crop_type = ? AND is_current = 1
                       """, (market_id, crop_type))

        # Insert new price
        cursor.execute("""
                       INSERT INTO market_prices (market_id, crop_type, price, unit, grade,
                                                  date_recorded, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       """, (market_id, crop_type, price, unit, grade, date_recorded, notes))

        price_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return price_id

    def get_market_prices_by_crop(self, crop_type, current_only=True):
        """Get all prices for a specific crop"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if current_only:
            cursor.execute("""
                           SELECT mp.*, m.name as market_name, m.location as market_location
                           FROM market_prices mp
                                    JOIN markets m ON mp.market_id = m.id
                           WHERE mp.crop_type = ? AND mp.is_current = 1 AND m.is_active = 1
                           ORDER BY mp.price DESC
                           """, (crop_type,))
        else:
            cursor.execute("""
                           SELECT mp.*, m.name as market_name, m.location as market_location
                           FROM market_prices mp
                                    JOIN markets m ON mp.market_id = m.id
                           WHERE mp.crop_type = ? AND m.is_active = 1
                           ORDER BY mp.date_recorded DESC
                           """, (crop_type,))

        prices = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return prices

    def get_price_history(self, market_id, crop_type, days=30):
        """Get price history for a market and crop"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       SELECT * FROM market_prices
                       WHERE market_id = ? AND crop_type = ?
                       ORDER BY date_recorded DESC
                           LIMIT ?
                       """, (market_id, crop_type, days))
        prices = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return prices

    def update_market_price(self, price_id, **kwargs):
        """Update market price"""
        updates = []
        params = []

        for key, value in kwargs.items():
            if value is not None:
                updates.append(f"{key} = ?")
                params.append(value)

        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(price_id)

        conn = self.get_connection()
        cursor = conn.cursor()
        query = f"UPDATE market_prices SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, tuple(params))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        return rows_affected > 0

    def delete_market_price(self, price_id):
        """Delete market price"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM market_prices WHERE id = ?", (price_id,))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        return rows_affected > 0

    # ==========================================
    # COLLECTION CENTER CRUD OPERATIONS
    # ==========================================

    def add_collection_center(self, name, location=None, latitude=None, longitude=None,
                              crops_accepted=None, contact_phone=None, contact_person=None,
                              operating_days=None, operating_hours=None, storage_capacity=None,
                              payment_terms=None, minimum_quantity=None, quality_requirements=None):
        """Add new collection center"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Convert crops_accepted list to JSON string
        crops_json = json.dumps(crops_accepted) if crops_accepted else None

        cursor.execute("""
                       INSERT INTO collection_centers (name, location, latitude, longitude,
                                                       crops_accepted, contact_phone, contact_person, operating_days,
                                                       operating_hours, storage_capacity, payment_terms, minimum_quantity,
                                                       quality_requirements)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       """, (name, location, latitude, longitude, crops_json, contact_phone,
                             contact_person, operating_days, operating_hours, storage_capacity,
                             payment_terms, minimum_quantity, quality_requirements))

        center_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return center_id

    def get_all_collection_centers(self, active_only=True):
        """Get all collection centers"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if active_only:
            cursor.execute("SELECT * FROM collection_centers WHERE is_active = 1 ORDER BY name")
        else:
            cursor.execute("SELECT * FROM collection_centers ORDER BY name")

        centers = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Parse JSON crops_accepted
        for center in centers:
            if center.get('crops_accepted'):
                center['crops_accepted'] = json.loads(center['crops_accepted'])

        return centers

    def get_collection_center(self, center_id):
        """Get single collection center by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM collection_centers WHERE id = ?", (center_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            center = dict(row)
            if center.get('crops_accepted'):
                center['crops_accepted'] = json.loads(center['crops_accepted'])
            return center
        return None

    def get_collection_centers_by_crop(self, crop_type, active_only=True):
        """Get collection centers that accept a specific crop"""
        centers = self.get_all_collection_centers(active_only)
        filtered = [c for c in centers if crop_type.lower() in [crop.lower() for crop in (c.get('crops_accepted') or [])]]
        return filtered

    def update_collection_center(self, center_id, **kwargs):
        """Update collection center"""
        updates = []
        params = []

        for key, value in kwargs.items():
            if value is not None:
                # Handle crops_accepted list
                if key == 'crops_accepted' and isinstance(value, list):
                    value = json.dumps(value)
                updates.append(f"{key} = ?")
                params.append(value)

        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(center_id)

        conn = self.get_connection()
        cursor = conn.cursor()
        query = f"UPDATE collection_centers SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, tuple(params))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        return rows_affected > 0

    def delete_collection_center(self, center_id):
        """Soft delete collection center"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       UPDATE collection_centers SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?
                       """, (center_id,))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        return rows_affected > 0