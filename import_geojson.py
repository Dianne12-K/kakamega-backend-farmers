import json
from database import Database

def import_farms_from_geojson(geojson_path):
    """Import farms from GeoJSON file into database"""

    # Initialize database
    db = Database()
    db.update_schema()  # Add new columns if needed

    # Load GeoJSON
    with open(geojson_path, 'r', encoding='utf-8') as f:
        geojson_data = json.load(f)

    imported_count = 0

    # Process each feature
    for feature in geojson_data['features']:
        props = feature['properties']
        geometry = feature['geometry']

        # Extract properties
        name = props.get('name', 'Unknown Farm')
        crop_type = props.get('crop_type')
        planting_date = props.get('planting_date')
        area_ha = props.get('area_ha')
        latitude = props.get('latitude')
        longitude = props.get('longitude')
        soil_type = props.get('soil_type')
        irrigation = props.get('irrigation')
        fertilizer_used = props.get('fertilizer_used')
        yield_estimate_tons = props.get('yield_estimate_tons')
        status = props.get('status')

        # Store the geometry as boundary_geojson
        boundary_geojson = geometry

        try:
            farm_id = db.add_farm(
                name=name,
                crop_type=crop_type,
                planting_date=planting_date,
                area_ha=area_ha,
                lat=latitude,
                lon=longitude,
                boundary_geojson=boundary_geojson,
                soil_type=soil_type,
                irrigation=irrigation,
                fertilizer_used=fertilizer_used,
                yield_estimate_tons=yield_estimate_tons,
                status=status
            )
            print(f"✓ Imported: {name} (ID: {farm_id})")
            imported_count += 1
        except Exception as e:
            print(f"✗ Failed to import {name}: {str(e)}")

    print(f"\n{'='*50}")
    print(f"Total farms imported: {imported_count}/{len(geojson_data['features'])}")
    print(f"{'='*50}")

if __name__ == "__main__":
    geojson_file = r"C:\Users\Diana.Khayenzeli\IdeaProjects\Geovisualize\farm_data_updated.geojson"
    import_farms_from_geojson(geojson_file)