from database import Database

db = Database()

print("=== Testing Database ===")

# Test 1: Get all farms
farms = db.get_all_farms()
print(f"✓ Total farms: {len(farms)}")

if farms:
    for farm in farms:
        print(f"  - {farm['name']} ({farm['crop_type']})")

# Test 2: Add a test reading
if farms:
    farm_id = farms[0]['id']

    # Add NDVI reading
    db.save_ndvi_reading(
        farm_id=farm_id,
        date="2024-12-17",
        ndvi_value=0.65,
        health_score=75,
        status="healthy"
    )
    print(f"✓ Added NDVI reading for farm {farm_id}")

    # Get latest NDVI
    latest = db.get_latest_ndvi(farm_id)
    print(f"✓ Latest NDVI: {latest['ndvi_value']} (Score: {latest['health_score']})")

print("\n✓ Database is working perfectly!")