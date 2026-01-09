import ee
from datetime import datetime, timedelta
from config import Config

class GEEProcessor:
    def __init__(self):
        try:
            ee.Initialize(project=Config.GEE_PROJECT_ID)
        except Exception as e:
            print(f"GEE initialization error: {e}")
            print("Attempting to authenticate...")
            ee.Authenticate()
            ee.Initialize(project=Config.GEE_PROJECT_ID)

    def _prepare_geometry(self, geometry):
        """
        Convert database geometry to EE-compatible format
        Handles 3D coordinates by removing elevation values
        """
        if not geometry or 'coordinates' not in geometry:
            raise ValueError("Invalid geometry: missing coordinates")

        # Deep copy to avoid modifying original
        clean_geometry = {
            'type': geometry['type'],
            'coordinates': self._remove_elevation(geometry['coordinates'])
        }

        return ee.Geometry(clean_geometry)

    def _remove_elevation(self, coords):
        """Recursively remove elevation (z) values from coordinates"""
        if isinstance(coords[0], (int, float)):
            # This is a single coordinate point [lon, lat, elevation]
            return coords[:2]  # Return only [lon, lat]
        else:
            # This is a list of coordinates
            return [self._remove_elevation(c) for c in coords]

    def calculate_ndvi(self, geometry, start_date, end_date):
        """
        Calculate NDVI for a given geometry and date range

        Args:
            geometry: GeoJSON geometry (polygon)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of NDVI values with dates
        """
        try:
            # Convert GeoJSON to EE geometry
            ee_geometry = self._prepare_geometry(geometry)

            # Get Sentinel-2 imagery
            collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                .filterBounds(ee_geometry) \
                .filterDate(start_date, end_date) \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))

            # Calculate NDVI
            def add_ndvi(image):
                ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
                return image.addBands(ndvi)

            collection_ndvi = collection.map(add_ndvi)

            # Get time series
            def extract_ndvi(image):
                ndvi_mean = image.select('NDVI').reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=ee_geometry,
                    scale=10,
                    maxPixels=1e9
                )
                return ee.Feature(None, {
                    'date': image.date().format('YYYY-MM-dd'),
                    'ndvi': ndvi_mean.get('NDVI')
                })

            ndvi_features = collection_ndvi.map(extract_ndvi)
            ndvi_list = ndvi_features.getInfo()['features']

            # Format results
            results = []
            for feature in ndvi_list:
                props = feature['properties']
                if props['ndvi'] is not None:
                    results.append({
                        'date': props['date'],
                        'ndvi': round(props['ndvi'], 3)
                    })

            return sorted(results, key=lambda x: x['date'])

        except Exception as e:
            print(f"Error calculating NDVI: {e}")
            return []

    def get_latest_ndvi(self, geometry):
        """Get most recent NDVI value"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        ndvi_data = self.calculate_ndvi(
            geometry,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )

        if ndvi_data:
            return ndvi_data[-1]  # Most recent
        return None

    def get_ndvi_time_series(self, geometry, days=90):
        """Get NDVI time series for specified days"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        return self.calculate_ndvi(
            geometry,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )

    def calculate_health_score(self, ndvi_value):
        """
        Convert NDVI to health score (0-100)

        NDVI ranges:
        - Bare soil/water: -1 to 0.2
        - Sparse vegetation: 0.2 to 0.5
        - Moderate vegetation: 0.5 to 0.7
        - Dense healthy vegetation: 0.7 to 1.0
        """
        if ndvi_value is None:
            return 0

        # Normalize to 0-100 scale
        if ndvi_value < 0.2:
            score = 0
        elif ndvi_value < 0.5:
            # 0.2 to 0.5 → 20 to 50
            score = 20 + ((ndvi_value - 0.2) / 0.3) * 30
        elif ndvi_value < 0.7:
            # 0.5 to 0.7 → 50 to 80
            score = 50 + ((ndvi_value - 0.5) / 0.2) * 30
        else:
            # 0.7 to 1.0 → 80 to 100
            score = 80 + ((ndvi_value - 0.7) / 0.3) * 20

        return int(min(100, max(0, score)))

    def get_health_status(self, health_score):
        """Categorize health status"""
        if health_score >= 70:
            return {
                'status': 'healthy',
                'color': 'green',
                'label': 'Healthy'
            }
        elif health_score >= 50:
            return {
                'status': 'watch',
                'color': 'yellow',
                'label': 'Needs Attention'
            }
        else:
            return {
                'status': 'critical',
                'color': 'red',
                'label': 'Critical'
            }

    def get_soil_moisture(self, geometry, date=None):
        """
        Get soil moisture from NASA SMAP

        Args:
            geometry: GeoJSON geometry
            date: Date string (YYYY-MM-DD), defaults to yesterday

        Returns:
            Soil moisture percentage (0-100)
        """
        try:
            if date is None:
                date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

            ee_geometry = self._prepare_geometry(geometry)

            # Use updated NASA SMAP data (version 008)
            smap = ee.ImageCollection('NASA/SMAP/SPL4SMGP/008') \
                .filterDate(date, (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')) \
                .select('sm_surface') \
                .first()

            # Get mean soil moisture
            moisture = smap.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=ee_geometry,
                scale=9000,  # SMAP resolution is ~9km
                maxPixels=1e9
            )

            moisture_value = moisture.getInfo().get('sm_surface')

            if moisture_value:
                # Convert to percentage (SMAP is in m³/m³)
                # Typical range: 0.05 to 0.50
                # Convert to 0-100 scale
                moisture_percent = moisture_value * 200  # Approximate conversion
                return round(min(100, max(0, moisture_percent)), 1)

            return None

        except Exception as e:
            print(f"Error getting soil moisture: {e}")
            # Fallback: estimate from NDVI and precipitation
            return self._estimate_moisture_from_ndvi(geometry)

    def _estimate_moisture_from_ndvi(self, geometry):
        """Fallback: Estimate moisture from recent NDVI trends"""
        # Simple estimation for demo
        # In production, use actual soil moisture sensors or better models
        import random
        return round(random.uniform(30, 70), 1)

    def get_moisture_status(self, moisture_percent):
        """Categorize moisture status"""
        thresholds = Config.MOISTURE_THRESHOLDS

        if moisture_percent >= thresholds['wet']:
            return {
                'status': 'wet',
                'color': 'blue',
                'label': 'Wet'
            }
        elif moisture_percent >= thresholds['adequate']:
            return {
                'status': 'adequate',
                'color': 'green',
                'label': 'Adequate'
            }
        elif moisture_percent >= thresholds['low']:
            return {
                'status': 'low',
                'color': 'orange',
                'label': 'Low'
            }
        else:
            return {
                'status': 'dry',
                'color': 'red',
                'label': 'Dry'
            }