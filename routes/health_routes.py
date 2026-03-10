"""
routes/health_routes.py
------------------------
Crop health (NDVI) and soil moisture endpoints.
Migrated to SQLAlchemy + PostGIS.
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, date
from extensions import db
from core.models import Farm, NDVIReading, MoistureReading
from gee_processing import GEEProcessor

health_bp = Blueprint('health', __name__)
gee = GEEProcessor()


@health_bp.route('/api/health', methods=['GET'])
def api_health():
    """
    API Health Check
    ---
    tags:
      - Health
    responses:
      200:
        description: API is running
    """
    try:
        # Quick DB check
        db.session.execute(db.text('SELECT 1'))
        return jsonify({
            'success':  True,
            'status':   'healthy',
            'database': 'PostgreSQL + PostGIS connected',
            'time':     datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'status': 'unhealthy', 'error': str(e)}), 500


@health_bp.route('/api/farms/<int:farm_id>/health', methods=['GET'])
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
    responses:
      200:
        description: NDVI health data + time series
      404:
        description: Farm not found
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        days = int(request.args.get('days', 90))

        # Get NDVI time series from GEE
        geometry = None
        if farm.boundary:
            from sqlalchemy import func
            geometry = db.session.scalar(func.ST_AsGeoJSON(farm.boundary))
        elif farm.latitude and farm.longitude:
            geometry = {
                'type': 'Point',
                'coordinates': [float(farm.longitude), float(farm.latitude)]
            }

        ndvi_data    = gee.get_ndvi_time_series(geometry, days=days) if geometry else []
        health_score = 0
        health_status = None

        if ndvi_data:
            latest       = ndvi_data[-1]
            health_score = gee.calculate_health_score(latest['ndvi'])
            health_status = gee.get_health_status(health_score)

            # Save latest reading to DB
            reading = NDVIReading(
                farm_id      = farm_id,
                date         = date.fromisoformat(latest['date']),
                ndvi_value   = latest['ndvi'],
                health_score = health_score,
                status       = health_status['status'],
                source       = 'sentinel-2'
            )
            db.session.add(reading)
            db.session.commit()

        return jsonify({
            'success':       True,
            'farm_id':       farm_id,
            'farm_name':     farm.name,
            'time_series':   ndvi_data,
            'latest':        ndvi_data[-1] if ndvi_data else None,
            'health_score':  health_score,
            'health_status': health_status,
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@health_bp.route('/api/farms/<int:farm_id>/moisture', methods=['GET'])
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
        description: Soil moisture reading
      404:
        description: Farm not found
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        geometry = None
        if farm.boundary:
            from sqlalchemy import func
            geometry = db.session.scalar(func.ST_AsGeoJSON(farm.boundary))
        elif farm.latitude and farm.longitude:
            geometry = {'type': 'Point', 'coordinates': [float(farm.longitude), float(farm.latitude)]}

        moisture_percent = gee.get_soil_moisture(geometry) if geometry else 0
        moisture_status  = gee.get_moisture_status(moisture_percent)

        # Save reading
        reading = MoistureReading(
            farm_id          = farm_id,
            date             = date.today(),
            moisture_percent = moisture_percent,
            status           = moisture_status['status'],
            days_since_rain  = 0
        )
        db.session.add(reading)
        db.session.commit()

        return jsonify({
            'success':         True,
            'farm_id':         farm_id,
            'farm_name':       farm.name,
            'moisture_percent': moisture_percent,
            'moisture_status': moisture_status,
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@health_bp.route('/api/farms/<int:farm_id>/ndvi-history', methods=['GET'])
def get_ndvi_history(farm_id):
    """
    Get NDVI History from Database
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
    responses:
      200:
        description: NDVI history from DB
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        days  = int(request.args.get('days', 90))
        since = datetime.utcnow().date() - __import__('datetime').timedelta(days=days)

        readings = (NDVIReading.query
                    .filter_by(farm_id=farm_id)
                    .filter(NDVIReading.date >= since)
                    .order_by(NDVIReading.date.asc())
                    .all())

        return jsonify({
            'success':  True,
            'farm_id':  farm_id,
            'days':     days,
            'count':    len(readings),
            'history':  [r.to_dict() for r in readings],
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500