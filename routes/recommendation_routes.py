from flask import Blueprint, jsonify
from database import Database
from gee_processing import GEEProcessor
from weather_api import WeatherAPI
from recommendation_engine import RecommendationEngine

recommendation_bp = Blueprint('recommendations', __name__, url_prefix='/api')
db = Database()
gee = GEEProcessor()
weather = WeatherAPI()
recommender = RecommendationEngine()

@recommendation_bp.route('/farms/<int:farm_id>/recommendation', methods=['GET'])
def get_farm_recommendation(farm_id):
    """
    Get Smart Farming Recommendation
    ---
    tags:
      - Recommendations
    parameters:
      - name: farm_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Smart recommendation
      404:
        description: Farm not found
    """
    try:
        farm = db.get_farm(farm_id)

        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        geometry = farm['boundary_geojson']

        # Get health data
        latest_ndvi = gee.get_latest_ndvi(geometry)
        if latest_ndvi:
            health_score = gee.calculate_health_score(latest_ndvi['ndvi'])
            health_trend = 'stable'
        else:
            health_score = 0
            health_trend = 'unknown'

        health_data = {
            'ndvi': latest_ndvi['ndvi'] if latest_ndvi else 0,
            'health_score': health_score,
            'trend': health_trend
        }

        # Get moisture data
        moisture_percent = gee.get_soil_moisture(geometry)
        moisture_status_obj = gee.get_moisture_status(moisture_percent)

        moisture_data = {
            'moisture_percent': moisture_percent,
            'status': moisture_status_obj['status']
        }

        # Get weather data
        lat = farm['latitude']
        lon = farm['longitude']
        forecast = weather.get_forecast(lat, lon, days=7)

        weather_data = {'forecast': forecast}

        # Farm info
        farm_info = {
            'crop_type': farm['crop_type'],
            'planting_date': farm['planting_date'],
            'area_ha': farm['area_ha']
        }

        # Generate recommendation
        recommendation = recommender.generate_recommendation(
            health_data=health_data,
            moisture_data=moisture_data,
            weather_data=weather_data,
            farm_info=farm_info
        )

        # Save to database
        db.save_recommendation(
            farm_id=farm_id,
            priority=recommendation['priority'],
            action=recommendation['action'],
            reason=recommendation['reason']
        )

        return jsonify({
            'success': True,
            'farm_id': farm_id,
            'farm_name': farm['name'],
            'recommendation': recommendation,
            'data_used': {
                'health': health_data,
                'moisture': moisture_data,
                'weather_summary': {
                    'days_forecasted': len(forecast),
                    'total_rain_expected': sum(d['rain_mm'] for d in forecast)
                }
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@recommendation_bp.route('/farms/<int:farm_id>/irrigation-schedule', methods=['GET'])
def get_irrigation_schedule(farm_id):
    """
    Get 7-Day Irrigation Schedule
    ---
    tags:
      - Recommendations
    parameters:
      - name: farm_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Irrigation schedule
      404:
        description: Farm not found
    """
    try:
        farm = db.get_farm(farm_id)

        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        # Get data
        geometry = farm['boundary_geojson']
        moisture_percent = gee.get_soil_moisture(geometry)
        moisture_status_obj = gee.get_moisture_status(moisture_percent)

        moisture_data = {
            'moisture_percent': moisture_percent,
            'status': moisture_status_obj['status']
        }

        lat = farm['latitude']
        lon = farm['longitude']
        forecast = weather.get_forecast(lat, lon, days=7)

        weather_data = {'forecast': forecast}

        farm_info = {
            'crop_type': farm['crop_type'],
            'planting_date': farm['planting_date']
        }

        # Generate schedule
        schedule = recommender.get_irrigation_schedule(
            farm_info=farm_info,
            moisture_data=moisture_data,
            weather_data=weather_data
        )

        return jsonify({
            'success': True,
            'farm_id': farm_id,
            'farm_name': farm['name'],
            'schedule': schedule
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500