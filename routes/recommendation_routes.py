"""
routes/recommendation_routes.py
---------------------------------
AI-powered farm recommendations — migrated to SQLAlchemy.
"""
from flask import Blueprint, jsonify
from extensions import db
from core.models import Farm, Recommendation
from gee_processing import GEEProcessor
from weather_api import WeatherAPI
from recommendation_engine import RecommendationEngine
from sqlalchemy import func

recommendation_bp = Blueprint('recommendations', __name__)
gee         = GEEProcessor()
weather_api = WeatherAPI()
recommender = RecommendationEngine()


def _get_geometry(farm):
    """Return GeoJSON geometry dict from farm model."""
    if farm.boundary:
        return db.session.scalar(func.ST_AsGeoJSON(farm.boundary))
    if farm.latitude and farm.longitude:
        return {'type': 'Point', 'coordinates': [float(farm.longitude), float(farm.latitude)]}
    return None


@recommendation_bp.route('/farms/<int:farm_id>/recommendation', methods=['GET'])
def get_farm_recommendation(farm_id):
    """
    Get AI Smart Farming Recommendation
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
        description: Recommendation with health, moisture and weather context
      404:
        description: Farm not found
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        geometry = _get_geometry(farm)

        # ── Health data ────────────────────────────────────────
        latest_ndvi  = gee.get_latest_ndvi(geometry) if geometry else None
        health_score = gee.calculate_health_score(latest_ndvi['ndvi']) if latest_ndvi else 0
        health_data  = {
            'ndvi':         latest_ndvi['ndvi'] if latest_ndvi else 0,
            'health_score': health_score,
            'trend':        'stable'
        }

        # ── Moisture data ──────────────────────────────────────
        moisture_pct    = gee.get_soil_moisture(geometry) if geometry else 0
        moisture_status = gee.get_moisture_status(moisture_pct)
        moisture_data   = {'moisture_percent': moisture_pct, 'status': moisture_status['status']}

        # ── Weather data ───────────────────────────────────────
        lat      = float(farm.latitude)  if farm.latitude  else 0.2827
        lon      = float(farm.longitude) if farm.longitude else 34.7519
        forecast = weather_api.get_forecast(lat, lon, days=7)
        weather_data = {'forecast': forecast}

        # ── Generate recommendation ────────────────────────────
        farm_info = {
            'crop_type':    farm.crop_type,
            'planting_date': str(farm.planting_date) if farm.planting_date else None,
            'area_ha':      float(farm.area_ha) if farm.area_ha else None,
        }
        rec = recommender.generate_recommendation(
            health_data=health_data,
            moisture_data=moisture_data,
            weather_data=weather_data,
            farm_info=farm_info
        )

        # ── Save to DB ─────────────────────────────────────────
        db_rec = Recommendation(
            farm_id  = farm_id,
            priority = rec.get('priority'),
            action   = rec.get('action'),
            reason   = rec.get('reason'),
            category = rec.get('category'),
        )
        db.session.add(db_rec)
        db.session.commit()

        return jsonify({
            'success':    True,
            'farm_id':    farm_id,
            'farm_name':  farm.name,
            'recommendation': rec,
            'data_used': {
                'health':   health_data,
                'moisture': moisture_data,
                'weather_summary': {
                    'days_forecasted':     len(forecast),
                    'total_rain_expected': sum(d.get('rain_mm', 0) for d in forecast),
                }
            }
        })

    except Exception as e:
        db.session.rollback()
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
        description: Daily irrigation schedule
      404:
        description: Farm not found
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        geometry        = _get_geometry(farm)
        moisture_pct    = gee.get_soil_moisture(geometry) if geometry else 0
        moisture_status = gee.get_moisture_status(moisture_pct)
        moisture_data   = {'moisture_percent': moisture_pct, 'status': moisture_status['status']}

        lat      = float(farm.latitude)  if farm.latitude  else 0.2827
        lon      = float(farm.longitude) if farm.longitude else 34.7519
        forecast = weather_api.get_forecast(lat, lon, days=7)

        schedule = recommender.get_irrigation_schedule(
            farm_info     = {'crop_type': farm.crop_type, 'planting_date': str(farm.planting_date)},
            moisture_data = moisture_data,
            weather_data  = {'forecast': forecast}
        )

        return jsonify({
            'success':   True,
            'farm_id':   farm_id,
            'farm_name': farm.name,
            'schedule':  schedule,
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@recommendation_bp.route('/farms/<int:farm_id>/history', methods=['GET'])
def get_recommendation_history(farm_id):
    """
    Get Recommendation History for a Farm
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
        description: Past recommendations
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        recs = (Recommendation.query
                .filter_by(farm_id=farm_id)
                .order_by(Recommendation.created_at.desc())
                .limit(20).all())

        return jsonify({'success': True, 'farm_id': farm_id, 'count': len(recs),
                        'recommendations': [r.to_dict() for r in recs]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500