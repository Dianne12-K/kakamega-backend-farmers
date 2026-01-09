# check_data.py
from database import Database

db = Database()

print("Checking NDVI data in database...")
print("=" * 60)

farms = db.get_all_farms()

for farm in farms[:5]:  # Check first 5 farms
    print(f"\n{farm['name']} (ID: {farm['id']})")

    # Check NDVI
    ndvi = db.get_latest_ndvi(farm['id'])
    if ndvi:
        print(f"  ✓ NDVI: {ndvi}")
    else:
        print(f"  ✗ No NDVI data")

    # Check Moisture
    moisture = db.get_latest_moisture(farm['id'])
    if moisture:
        print(f"  ✓ Moisture: {moisture}")
    else:
        print(f"  ✗ No moisture data")

print("\n" + "=" * 60)