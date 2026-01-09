import ee

print("Testing different initialization methods...")

# Method 1: Using project parameter
try:
    ee.Initialize(project='healthfacilities')
    print("✓ Method 1 SUCCESS: ee.Initialize(project='healthfacilities')")
except Exception as e:
    print(f"✗ Method 1 FAILED: {e}")

# Method 2: Using opt_url
try:
    ee.Initialize(opt_url='https://earthengine-highvolume.googleapis.com')
    print("✓ Method 2 SUCCESS: Using high-volume endpoint")
except Exception as e:
    print(f"✗ Method 2 FAILED: {e}")

# Method 3: Default initialization
try:
    ee.Initialize()
    print("✓ Method 3 SUCCESS: Default initialization")
except Exception as e:
    print(f"✗ Method 3 FAILED: {e}")

# Test if it actually works
try:
    image = ee.Image('COPERNICUS/S2_SR_HARMONIZED/20230101T073201_20230101T073201_T36MZE')
    print("✓ Can access satellite data!")
except Exception as e:
    print(f"✗ Cannot access data: {e}")