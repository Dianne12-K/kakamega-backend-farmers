"""Weather and Recommendation database operations"""


class WeatherMixin:
    """Mixin for Weather and Recommendation operations"""

    # ===== WEATHER OPERATIONS =====

    def save_weather_forecast(self, lat, lon, forecast_data):
        """Save weather forecast data"""
        with self.transaction() as conn:
            cursor = conn.cursor()

            for day in forecast_data:
                cursor.execute("""
                               INSERT INTO weather_data
                               (latitude, longitude, date, temperature, humidity,
                                rain_probability, rain_amount, conditions)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                               """, (
                                   lat, lon, day["date"], day["temp"], day["humidity"],
                                   day["rain_prob"], day["rain_mm"], day["conditions"]
                               ))

    def get_weather_forecast(self, lat, lon, days=7):
        """Get weather forecast for location"""
        query = """
                SELECT * FROM weather_data
                WHERE latitude = ? AND longitude = ?
                ORDER BY date ASC
                    LIMIT ? \
                """
        return self.execute_query(query, (lat, lon, days))

    # ===== RECOMMENDATION OPERATIONS =====

    def save_recommendation(self, farm_id, priority, action, reason):
        """Save recommendation for a farm"""
        with self.transaction() as conn:
            cursor = conn.cursor()

            # Delete old recommendations
            cursor.execute("DELETE FROM recommendations WHERE farm_id = ?", (farm_id,))

            # Insert new recommendation
            cursor.execute("""
                           INSERT INTO recommendations (farm_id, priority, action, reason)
                           VALUES (?, ?, ?, ?)
                           """, (farm_id, priority, action, reason))

    def get_recommendation(self, farm_id):
        """Get latest recommendation for a farm"""
        query = """
                SELECT * FROM recommendations
                WHERE farm_id = ?
                ORDER BY created_at DESC
                    LIMIT 1 \
                """
        return self.execute_one(query, (farm_id,))