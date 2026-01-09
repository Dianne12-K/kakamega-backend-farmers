from gee_processing import GEEProcessor
from database import Database
from datetime import datetime, timedelta

class SatelliteService:
    def __init__(self):
        self.gee = GEEProcessor()
        self.db = Database()

    def update_farm_ndvi(self, farm_id):
        """Fetch and save NDVI data for a farm"""
        # Get farm from database
        farm = self.db.get_farm(farm_id)
        if not farm:
            return {"error": "Farm not found"}

        # Extract geometry from farm's boundary_geojson
        geometry = farm['boundary_geojson']

        # Get latest NDVI from GEE
        latest_ndvi = self.gee.get_latest_ndvi(geometry)

        if latest_ndvi:
            ndvi_value = latest_ndvi['ndvi']
            date = latest_ndvi['date']

            # Calculate health score and status
            health_score = self.gee.calculate_health_score(ndvi_value)
            health_status_info = self.gee.get_health_status(health_score)

            # Save to database
            self.db.save_ndvi_reading(
                farm_id=farm_id,
                date=date,
                ndvi_value=ndvi_value,
                health_score=health_score,
                status=health_status_info['status']
            )

            return {
                "success": True,
                "farm_id": farm_id,
                "farm_name": farm['name'],
                "ndvi": ndvi_value,
                "health_score": health_score,
                "status": health_status_info['label'],
                "date": date
            }

        return {"error": "No NDVI data available"}

    def update_farm_moisture(self, farm_id):
        """Fetch and save soil moisture data for a farm"""
        # Get farm from database
        farm = self.db.get_farm(farm_id)
        if not farm:
            return {"error": "Farm not found"}

        # Extract geometry
        geometry = farm['boundary_geojson']

        # Get soil moisture from GEE
        moisture_percent = self.gee.get_soil_moisture(geometry)

        if moisture_percent:
            date = datetime.now().strftime('%Y-%m-%d')

            # Get moisture status
            moisture_status_info = self.gee.get_moisture_status(moisture_percent)

            # Calculate days since rain (simplified - you'd get this from weather data)
            days_since_rain = 3  # Placeholder

            # Save to database
            self.db.save_moisture_reading(
                farm_id=farm_id,
                date=date,
                moisture_percent=moisture_percent,
                status=moisture_status_info['status'],
                days_since_rain=days_since_rain
            )

            return {
                "success": True,
                "farm_id": farm_id,
                "farm_name": farm['name'],
                "moisture_percent": moisture_percent,
                "status": moisture_status_info['label'],
                "date": date
            }

        return {"error": "No moisture data available"}

    def update_farm_time_series(self, farm_id, days=90):
        """Get NDVI time series for a farm"""
        farm = self.db.get_farm(farm_id)
        if not farm:
            return {"error": "Farm not found"}

        geometry = farm['boundary_geojson']

        # Get time series from GEE
        ndvi_series = self.gee.get_ndvi_time_series(geometry, days)

        # Save each reading to database
        for reading in ndvi_series:
            health_score = self.gee.calculate_health_score(reading['ndvi'])
            health_status_info = self.gee.get_health_status(health_score)

            self.db.save_ndvi_reading(
                farm_id=farm_id,
                date=reading['date'],
                ndvi_value=reading['ndvi'],
                health_score=health_score,
                status=health_status_info['status']
            )

        return {
            "success": True,
            "farm_id": farm_id,
            "readings_saved": len(ndvi_series),
            "date_range": f"{ndvi_series[0]['date']} to {ndvi_series[-1]['date']}" if ndvi_series else None
        }

    def update_all_farms(self):
        """Update NDVI and moisture for all farms"""
        farms = self.db.get_all_farms()
        results = []

        for farm in farms:
            print(f"Processing {farm['name']}...")

            # Update NDVI
            ndvi_result = self.update_farm_ndvi(farm['id'])

            # Update moisture
            moisture_result = self.update_farm_moisture(farm['id'])

            results.append({
                "farm_id": farm['id'],
                "farm_name": farm['name'],
                "ndvi": ndvi_result,
                "moisture": moisture_result
            })

        return results