import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ── Flask ──────────────────────────────────────────────────
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'True') == 'True'

    # ── PostgreSQL + PostGIS ───────────────────────────────────
    DB_HOST     = os.getenv('DB_HOST', 'localhost')
    DB_PORT     = os.getenv('DB_PORT', '5432')
    DB_NAME     = os.getenv('DB_NAME', 'kakamega_smart_farm')
    DB_USER     = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # ── API Keys ───────────────────────────────────────────────
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '')

    # ── Google Earth Engine ────────────────────────────────────
    GEE_PROJECT_ID      = os.getenv('GEE_PROJECT_ID', '')
    GEE_SERVICE_ACCOUNT = os.getenv('GEE_SERVICE_ACCOUNT', '')
    GEE_KEY_FILE        = os.getenv('GEE_KEY_FILE', 'gee_key.json')

    # ── Kakamega County Defaults ───────────────────────────────
    DEFAULT_LAT = 0.2827
    DEFAULT_LON = 34.7519

    # ── NDVI Thresholds ────────────────────────────────────────
    NDVI_THRESHOLDS = {
        'critical': 0.3,
        'watch':    0.5,
        'healthy':  0.7
    }

    # ── Moisture Thresholds ────────────────────────────────────
    MOISTURE_THRESHOLDS = {
        'dry':      20,
        'low':      40,
        'adequate': 60,
        'wet':      80
    }

    # ── Paths ──────────────────────────────────────────────────
    FARMS_GEOJSON_PATH = os.getenv('FARMS_GEOJSON_PATH', 'data/farms.geojson')

    # ── Data refresh interval (hours) ─────────────────────────
    DATA_REFRESH_INTERVAL = int(os.getenv('DATA_REFRESH_INTERVAL', 24))


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 10,
        "max_overflow": 20,
    }


class TestingConfig(Config):
    TESTING = True
    DB_NAME = 'kakamega_smart_farm_test'
    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://postgres:postgres@localhost:5432/kakamega_smart_farm_test"
    )


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'testing':     TestingConfig,
    'default':     DevelopmentConfig
}