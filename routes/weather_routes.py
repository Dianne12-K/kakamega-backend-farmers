"""
routes/weather_routes.py
-------------------------
Weather endpoints — no DB changes needed, just cleaned up imports.
"""
from flask import Blueprint, request, jsonify
from config import config
from weather_api import WeatherAPI
from extensions import db
from core.models import WeatherData
from datetime import date

weather_bp  = Blueprint('weather', __name__)
weather_api = WeatherAPI()
cfg         = config['development']


@weather_bp.route('/', methods=['GET'])
def get_weather():
    """
    Get Current Weather + Forecast
    ---
    tags:
      - Weather
    parameters:
      - name: lat
        in: query
        type: number
        default: 0.2827
      - name: lon
        in: query
        type: number
        default: 34.7519
      - name: days
        in: query
        type: integer
        default: 7
    responses:
      200:
        description: Current weather and forecast
    """
    try:
        lat  = float(request.args.get('lat',  cfg.DEFAULT_LAT))
        lon  = float(request.args.get('lon',  cfg.DEFAULT_LON))
        days = int(request.args.get('days', 7))

        current  = weather_api.get_current_weather(lat, lon)
        forecast = weather_api.get_forecast(lat, lon, days=days)

        # Save current reading to DB
        if current:
            reading = WeatherData(
                latitude         = lat,
                longitude        = lon,
                date             = date.today(),
                temperature      = current.get('temperature'),
                humidity         = current.get('humidity'),
                rain_probability = current.get('rain_probability', 0),
                rain_amount      = current.get('rain_amount', 0),
                conditions       = current.get('conditions'),
                source           = 'openweather',
            )
            db.session.add(reading)
            db.session.commit()

        return jsonify({
            'success':  True,
            'location': {'latitude': lat, 'longitude': lon},
            'current':  current,
            'forecast': forecast,
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@weather_bp.route('/history', methods=['GET'])
def weather_history():
    """
    Get Saved Weather History
    ---
    tags:
      - Weather
    parameters:
      - name: days
        in: query
        type: integer
        default: 7
    responses:
      200:
        description: Weather readings from DB
    """
    try:
        from datetime import datetime, timedelta
        days  = int(request.args.get('days', 7))
        since = datetime.utcnow().date() - timedelta(days=days)

        readings = (WeatherData.query
                    .filter(WeatherData.date >= since)
                    .order_by(WeatherData.date.desc())
                    .all())

        return jsonify({
            'success': True,
            'count':   len(readings),
            'history': [r.to_dict() for r in readings],
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500