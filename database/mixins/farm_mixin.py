"""Farm-related database operations"""
import json


class FarmMixin:
    """Mixin for Farm, NDVI, and Moisture operations"""

    # ===== FARM OPERATIONS =====

    def add_farm(self, name, crop_type, planting_date, area_ha, lat, lon,
                 boundary_geojson, soil_type=None, irrigation=None,
                 fertilizer_used=None, yield_estimate_tons=None,
                 status=None, ward_id=None):
        """Add a new farm"""
        query = """
                INSERT INTO farms (
                    name, crop_type, planting_date, area_ha, latitude, longitude,
                    boundary_geojson, soil_type, irrigation, fertilizer_used,
                    yield_estimate_tons, status, ward_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) \
                """
        params = (
            name, crop_type, planting_date, area_ha, lat, lon,
            json.dumps(boundary_geojson), soil_type, irrigation,
            fertilizer_used, yield_estimate_tons, status, ward_id
        )
        return self.execute_write(query, params)

    def get_all_farms(self):
        """Get all farms"""
        farms = self.execute_query("SELECT * FROM farms")
        for farm in farms:
            if farm.get("boundary_geojson"):
                farm["boundary_geojson"] = json.loads(farm["boundary_geojson"])
        return farms

    def get_farm(self, farm_id):
        """Get single farm by ID"""
        farm = self.execute_one("SELECT * FROM farms WHERE id = ?", (farm_id,))
        if farm and farm.get("boundary_geojson"):
            farm["boundary_geojson"] = json.loads(farm["boundary_geojson"])
        return farm

    def get_farms_by_ward(self, ward_id):
        """Get all farms in a ward"""
        farms = self.execute_query(
            "SELECT * FROM farms WHERE ward_id = ? ORDER BY name",
            (ward_id,)
        )
        for farm in farms:
            if farm.get("boundary_geojson"):
                farm["boundary_geojson"] = json.loads(farm["boundary_geojson"])
        return farms

    # ===== NDVI OPERATIONS =====

    def save_ndvi_reading(self, farm_id, date, ndvi_value, health_score, status):
        """Save an NDVI reading"""
        query = """
                INSERT INTO ndvi_readings (farm_id, date, ndvi_value, health_score, status)
                VALUES (?, ?, ?, ?, ?) \
                """
        return self.execute_write(query, (farm_id, date, ndvi_value, health_score, status))

    def get_latest_ndvi(self, farm_id):
        """Get latest NDVI reading for a farm"""
        query = """
                SELECT * FROM ndvi_readings
                WHERE farm_id = ?
                ORDER BY date DESC
                    LIMIT 1 \
                """
        return self.execute_one(query, (farm_id,))

    def get_ndvi_history(self, farm_id, days=90):
        """Get NDVI history for a farm"""
        query = """
                SELECT date, ndvi_value, health_score, status
                FROM ndvi_readings
                WHERE farm_id = ?
                ORDER BY date DESC
                    LIMIT ? \
                """
        rows = self.execute_query(query, (farm_id, days // 5))
        return list(reversed(rows))

    # ===== MOISTURE OPERATIONS =====

    def save_moisture_reading(self, farm_id, date, moisture_percent, status, days_since_rain):
        """Save a moisture reading"""
        query = """
                INSERT INTO moisture_readings
                    (farm_id, date, moisture_percent, status, days_since_rain)
                VALUES (?, ?, ?, ?, ?) \
                """
        return self.execute_write(query, (farm_id, date, moisture_percent, status, days_since_rain))

    def get_latest_moisture(self, farm_id):
        """Get latest moisture reading for a farm"""
        query = """
                SELECT * FROM moisture_readings
                WHERE farm_id = ?
                ORDER BY date DESC
                    LIMIT 1 \
                """
        return self.execute_one(query, (farm_id,))