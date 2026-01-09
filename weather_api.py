import requests
from datetime import datetime, timedelta
from config import Config

class WeatherAPI:
    def __init__(self):
        self.api_key = Config.OPENWEATHER_API_KEY
        self.base_url = "http://api.openweathermap.org/data/2.5"

    def get_forecast(self, lat, lon, days=7):
        """
        Get weather forecast for coordinates

        Args:
            lat: Latitude
            lon: Longitude
            days: Number of days (max 5 for free tier)

        Returns:
            List of daily forecasts
        """
        try:
            # Use 5-day forecast endpoint (free tier)
            url = f"{self.base_url}/forecast"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.api_key,
                'units': 'metric'  # Celsius
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Process forecast data
            forecast = self._process_forecast(data, days)
            return forecast

        except requests.exceptions.RequestException as e:
            print(f"Error fetching weather: {e}")
            return self._get_dummy_forecast(days)

    def _process_forecast(self, data, days):
        """Process OpenWeatherMap forecast data"""
        daily_forecast = {}

        for item in data['list']:
            date = datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d')

            if date not in daily_forecast:
                daily_forecast[date] = {
                    'date': date,
                    'temp_max': item['main']['temp_max'],
                    'temp_min': item['main']['temp_min'],
                    'humidity': item['main']['humidity'],
                    'rain_mm': 0,
                    'rain_prob': 0,
                    'conditions': item['weather'][0]['main'],
                    'description': item['weather'][0]['description'],
                    'icon': item['weather'][0]['icon']
                }
            else:
                # Update with max/min temps
                daily_forecast[date]['temp_max'] = max(
                    daily_forecast[date]['temp_max'],
                    item['main']['temp_max']
                )
                daily_forecast[date]['temp_min'] = min(
                    daily_forecast[date]['temp_min'],
                    item['main']['temp_min']
                )

            # Add rain data
            if 'rain' in item and '3h' in item['rain']:
                daily_forecast[date]['rain_mm'] += item['rain']['3h']

            # Rain probability (from pop field)
            if 'pop' in item:
                daily_forecast[date]['rain_prob'] = max(
                    daily_forecast[date]['rain_prob'],
                    int(item['pop'] * 100)
                )

        # Format for output
        result = []
        for date in sorted(daily_forecast.keys())[:days]:
            day_data = daily_forecast[date]
            result.append({
                'date': date,
                'day_name': datetime.strptime(date, '%Y-%m-%d').strftime('%A'),
                'temp': round((day_data['temp_max'] + day_data['temp_min']) / 2, 1),
                'temp_max': round(day_data['temp_max'], 1),
                'temp_min': round(day_data['temp_min'], 1),
                'humidity': day_data['humidity'],
                'rain_prob': day_data['rain_prob'],
                'rain_mm': round(day_data['rain_mm'], 1),
                'conditions': day_data['conditions'],
                'description': day_data['description'],
                'icon': self._get_weather_emoji(day_data['conditions'])
            })

        return result

    def _get_weather_emoji(self, condition):
        """Get emoji for weather condition"""
        emojis = {
            'Clear': '☀️',
            'Clouds': '☁️',
            'Rain': '🌧️',
            'Drizzle': '🌦️',
            'Thunderstorm': '⛈️',
            'Snow': '❄️',
            'Mist': '🌫️',
            'Fog': '🌫️'
        }
        return emojis.get(condition, '🌤️')

    def get_next_rain(self, forecast):
        """Find next significant rain event"""
        for i, day in enumerate(forecast):
            if day['rain_prob'] > 50 and day['rain_mm'] > 5:
                return {
                    'days_until': i,
                    'date': day['date'],
                    'probability': day['rain_prob'],
                    'amount': day['rain_mm']
                }
        return None

    def _get_dummy_forecast(self, days):
        """Fallback dummy data for demo/testing"""
        base_date = datetime.now()
        forecast = []

        for i in range(days):
            date = base_date + timedelta(days=i)
            forecast.append({
                'date': date.strftime('%Y-%m-%d'),
                'day_name': date.strftime('%A'),
                'temp': 26 + (i % 3),
                'temp_max': 28 + (i % 3),
                'temp_min': 24 + (i % 3),
                'humidity': 65 + (i * 2),
                'rain_prob': min(10 + (i * 15), 80),
                'rain_mm': 0 if i < 2 else (5 + i * 3),
                'conditions': 'Sunny' if i < 2 else 'Rain',
                'description': 'clear sky' if i < 2 else 'light rain',
                'icon': '☀️' if i < 2 else '🌧️'
            })

        return forecast