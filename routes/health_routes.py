from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from database import Database
from gee_processing import GEEProcessor

health_bp = Blueprint('health', __name__, url_prefix='/api')
db = Database()
gee = GEEProcessor()

@health_bp.route('/farms/<int:farm_id>/health', methods=['GET'])
def get_farm_health(farm_id):
    """
    Get Crop Health (NDVI) Data
    ---
    tags:
      - Health
    parameters:
      - name: farm_id
        in: path
        type: integer
        required: true
      - name: days
        in: query
        type: integer
        default: 90
        description: Number of days of historical data
    responses:
      200:
        description: Crop health data
      404:
        description: Farm not found
    """
    try:
        farm = db.get_farm(farm_id)

        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        days = int(request.args.get('days', 90))

        # Get NDVI data
        geometry = farm['boundary_geojson']
        ndvi_data = gee.get_ndvi_time_series(geometry, days=days)

        # Save latest reading
        if ndvi_data:
            latest = ndvi_data[-1]
            health_score = gee.calculate_health_score(latest['ndvi'])
            health_status = gee.get_health_status(health_score)

            db.save_ndvi_reading(
                farm_id=farm_id,
                date=latest['date'],
                ndvi_value=latest['ndvi'],
                health_score=health_score,
                status=health_status['status']
            )
        else:
            health_score = 0
            health_status = None

        return jsonify({
            'success': True,
            'farm_id': farm_id,
            'farm_name': farm['name'],
            'time_series': ndvi_data,
            'latest': ndvi_data[-1] if ndvi_data else None,
            'health_score': health_score,
            'health_status': health_status
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@health_bp.route('/farms/<int:farm_id>/moisture', methods=['GET'])
def get_farm_moisture(farm_id):
    """
    Get Soil Moisture Data
    ---
    tags:
      - Health
    parameters:
      - name: farm_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Soil moisture data
      404:
        description: Farm not found
    """
    try:
        farm = db.get_farm(farm_id)

        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        geometry = farm['boundary_geojson']
        moisture_percent = gee.get_soil_moisture(geometry)
        moisture_status = gee.get_moisture_status(moisture_percent)

        # Save to database
        db.save_moisture_reading(
            farm_id=farm_id,
            date=datetime.now().strftime('%Y-%m-%d'),
            moisture_percent=moisture_percent,
            status=moisture_status['status'],
            days_since_rain=0
        )

        return jsonify({
            'success': True,
            'farm_id': farm_id,
            'moisture_percent': moisture_percent,
            'moisture_status': moisture_status
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500