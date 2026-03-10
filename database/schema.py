"""Database schema definitions - all CREATE TABLE statements"""

TABLES = {
    'subcounties': """
                   CREATE TABLE IF NOT EXISTS subcounties (
                                                              id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                              name TEXT NOT NULL,
                                                              code TEXT,
                                                              description TEXT,
                                                              created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                                              updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                   )
                   """,

    'wards': """
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
             """,

    'farms': """
             CREATE TABLE IF NOT EXISTS farms (
                                                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                  name TEXT NOT NULL,
                                                  crop_type TEXT,
                                                  planting_date TEXT,
                                                  area_ha REAL,
                                                  latitude REAL,
                                                  longitude REAL,
                                                  boundary_geojson TEXT,
                                                  soil_type TEXT,
                                                  irrigation TEXT,
                                                  fertilizer_used TEXT,
                                                  yield_estimate_tons REAL,
                                                  status TEXT,
                                                  ward_id INTEGER,
                                                  created_at TEXT DEFAULT CURRENT_TIMESTAMP
             )
             """,

    'ndvi_readings': """
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
                     """,

    'moisture_readings': """
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
                         """,

    'weather_data': """
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
                    """,

    'recommendations': """
                       CREATE TABLE IF NOT EXISTS recommendations (
                                                                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                      farm_id INTEGER,
                                                                      priority TEXT,
                                                                      action TEXT,
                                                                      reason TEXT,
                                                                      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                                                      FOREIGN KEY (farm_id) REFERENCES farms (id)
                           )
                       """,

    'markets': """
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
               """,

    'market_prices': """
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
                     """,

    'collection_centers': """
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
                          """
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_wards_subcounty ON wards(subcounty_id)",
    "CREATE INDEX IF NOT EXISTS idx_farms_ward ON farms(ward_id)",
    "CREATE INDEX IF NOT EXISTS idx_market_prices_market ON market_prices(market_id)",
    "CREATE INDEX IF NOT EXISTS idx_market_prices_crop ON market_prices(crop_type)",
    "CREATE INDEX IF NOT EXISTS idx_market_prices_current ON market_prices(is_current)",
]