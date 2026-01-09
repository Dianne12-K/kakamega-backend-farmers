from flask import Blueprint, request, jsonify
from config import Config
from weather_api import WeatherAPI

weather_bp = Blueprint('weather', __name__, url_prefix='/api')
weather = WeatherAPI()

@weather_bp.route('/weather', methods=['GET'])
def get_weather():
    """
    Get Weather Forecast
    ---
    tags:
      - Weather
    parameters:
      - name: lat
        in: query
        type: number
        required: false
        default: 0.2827
      - name: lon
        in: query
        type: number
        required: false
        default: 34.7519
      - name: days
        in: query
        type: integer
        required: false
        default: 7
    responses:
      200:
        description: Weather forecast
    """
    try:
        lat = float(request.args.get('lat', Config.DEFAULT_LAT))
        lon = float(request.args.get('lon', Config.DEFAULT_LON))
        days = int(request.args.get('days', 7))

        current = weather.get_current_weather(lat, lon)
        forecast = weather.get_forecast(lat, lon, days=days)

        return jsonify({
            'success': True,
            'location': {'latitude': lat, 'longitude': lon},
            'current': current,
            'forecast': forecast
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500