import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
    DEBUG = True

    # Database
    DATABASE_PATH = 'data/farms.db'

    # API Keys
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')

    # Google Earth Engine
    GEE_PROJECT_ID = os.getenv('GEE_PROJECT_ID', None)

    # Application Settings
    FARMS_GEOJSON_PATH = 'data/farms.geojson'

    # Kakamega County Coordinates (center)
    DEFAULT_LAT = 0.2827
    DEFAULT_LON = 34.7519

    # Thresholds
    NDVI_THRESHOLDS = {
        'critical': 0.3,
        'watch': 0.5,
        'healthy': 0.7
    }

    MOISTURE_THRESHOLDS = {
        'dry': 20,
        'low': 40,
        'adequate': 60,
        'wet': 80
    }

    # Data refresh interval (hours)
    DATA_REFRESH_INTERVAL = 24