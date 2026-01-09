from database import Database

if __name__ == '__main__':
    db = Database()
    print("✓ Database initialized successfully!")
    print(f"✓ Database location: {db.db_path}")

    # Optional: Add a test farm
    farm_id = db.add_farm(
        name="Test Farm - Kakamega",
        crop_type="maize",
        planting_date="2024-06-15",
        area_ha=2.5,
        lat=0.2827,
        lon=34.7519,
        boundary_geojson={
            "type": "Polygon",
            "coordinates": [[
                [34.7519, 0.2827],
                [34.7529, 0.2827],
                [34.7529, 0.2837],
                [34.7519, 0.2837],
                [34.7519, 0.2827]
            ]]
        }
    )
    print(f"✓ Test farm created with ID: {farm_id}")