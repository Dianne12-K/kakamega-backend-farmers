from satellite_service import SatelliteService

def update_all_farms():
    """Update satellite data for all farms"""
    service = SatelliteService()

    print("Starting satellite data update for all farms...")
    print("=" * 60)

    results = service.update_all_farms()

    print("\n" + "=" * 60)
    print("UPDATE SUMMARY")
    print("=" * 60)

    for result in results:
        print(f"\n{result['farm_name']} (ID: {result['farm_id']})")

        # NDVI
        if result['ndvi'].get('success'):
            print(f"  ✓ NDVI: {result['ndvi']['ndvi']:.3f} | Health: {result['ndvi']['health_score']}/100 ({result['ndvi']['status']})")
        else:
            print(f"  ✗ NDVI: {result['ndvi'].get('error', 'Failed')}")

        # Moisture
        if result['moisture'].get('success'):
            print(f"  ✓ Moisture: {result['moisture']['moisture_percent']}% ({result['moisture']['status']})")
        else:
            print(f"  ✗ Moisture: {result['moisture'].get('error', 'Failed')}")

    print("\n" + "=" * 60)
    print(f"Processed {len(results)} farms")
    print("=" * 60)

def update_single_farm(farm_id):
    """Update satellite data for a single farm"""
    service = SatelliteService()

    print(f"Updating farm ID {farm_id}...")

    # Update NDVI
    ndvi_result = service.update_farm_ndvi(farm_id)
    print(f"NDVI: {ndvi_result}")

    # Update moisture
    moisture_result = service.update_farm_moisture(farm_id)
    print(f"Moisture: {moisture_result}")

    # Get time series (optional)
    # time_series = service.update_farm_time_series(farm_id, days=90)
    # print(f"Time series: {time_series}")

if __name__ == "__main__":
    # Update all farms
    update_all_farms()

    # Or update a single farm
    # update_single_farm(2)  # John Makokha's Farm