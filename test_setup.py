import os
from dotenv import load_dotenv

load_dotenv()

print("=== Configuration Test ===")
print(f"OpenWeather API Key: {'✓ Found' if os.getenv('OPENWEATHER_API_KEY') else '✗ Missing'}")
print(f"GEE Project ID: {os.getenv('GEE_PROJECT_ID', 'Not set (optional)')}")
print(f"Secret Key: {'✓ Found' if os.getenv('SECRET_KEY') else '✗ Using default'}")

# Test Earth Engine
try:
    import ee
    ee.Initialize()
    print("✓ Google Earth Engine: Working")
except Exception as e:
    print(f"✗ Google Earth Engine: {e}")