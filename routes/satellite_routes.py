"""
routes/satellite_routes.py
---------------------------
Satellite & Google Earth Engine (GEE) endpoints.
Fetches fresh imagery, indices, and stores results in PostGIS DB.
"""
from flask import Blueprint, request, jsonify
from datetime import date, datetime, timedelta
from extensions import db
from core.models import Farm, SatelliteImagery, NDVIReading, MoistureReading
from gee_processing import GEEProcessor
from sqlalchemy import func

satellite_bp = Blueprint('satellite', __name__)
gee = GEEProcessor()


def _get_geometry(farm):
    """Return GeoJSON geometry from farm model."""
    if farm.boundary:
        return db.session.scalar(func.ST_AsGeoJSON(farm.boundary))
    if farm.latitude and farm.longitude:
        return {
            'type': 'Point',
            'coordinates': [float(farm.longitude), float(farm.latitude)]
        }
    return None


# ── GET /api/satellite/farms/<id>/ndvi ───────────────────────────────────────

@satellite_bp.route('/farms/<int:farm_id>/ndvi', methods=['GET'])
def get_farm_ndvi(farm_id):
    """
    Get Fresh NDVI from Google Earth Engine
    ---
    tags:
      - Satellite
    parameters:
      - name: farm_id
        in: path
        type: integer
        required: true
      - name: days
        in: query
        type: integer
        default: 30
        description: Number of days to look back for imagery
    responses:
      200:
        description: Latest NDVI value with health interpretation
      404:
        description: Farm not found
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        days     = int(request.args.get('days', 30))
        geometry = _get_geometry(farm)

        if not geometry:
            return jsonify({'success': False, 'error': 'Farm has no spatial geometry. Add latitude/longitude first.'}), 400

        # Fetch from GEE
        ndvi_data    = gee.get_ndvi_time_series(geometry, days=days)
        latest       = ndvi_data[-1] if ndvi_data else None
        health_score = gee.calculate_health_score(latest['ndvi']) if latest else 0
        health_status = gee.get_health_status(health_score) if latest else None

        # Save to DB
        if latest:
            reading = NDVIReading(
                farm_id      = farm_id,
                date         = date.fromisoformat(latest['date']),
                ndvi_value   = latest['ndvi'],
                health_score = health_score,
                status       = health_status['status'] if health_status else None,
                source       = 'sentinel-2'
            )
            db.session.add(reading)
            db.session.commit()

        return jsonify({
            'success':      True,
            'farm_id':      farm_id,
            'farm_name':    farm.name,
            'source':       'Google Earth Engine / Sentinel-2',
            'days_queried': days,
            'latest_ndvi':  latest,
            'health_score': health_score,
            'health_status': health_status,
            'time_series':  ndvi_data,
            'total_images': len(ndvi_data),
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/satellite/farms/<id>/imagery ────────────────────────────────────

@satellite_bp.route('/farms/<int:farm_id>/imagery', methods=['GET'])
def get_farm_imagery(farm_id):
    """
    Get Latest Satellite Imagery Metadata
    ---
    tags:
      - Satellite
    parameters:
      - name: farm_id
        in: path
        type: integer
        required: true
      - name: satellite
        in: query
        type: string
        default: sentinel-2
        description: sentinel-2 | landsat-8 | landsat-9
    responses:
      200:
        description: Satellite imagery metadata for the farm
      404:
        description: Farm not found
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        satellite = request.args.get('satellite', 'sentinel-2')
        geometry  = _get_geometry(farm)

        if not geometry:
            return jsonify({'success': False, 'error': 'Farm has no spatial geometry'}), 400

        # Get imagery metadata from GEE
        imagery_meta = gee.get_latest_imagery(geometry, satellite=satellite)

        # Save to satellite_imagery table
        if imagery_meta:
            record = SatelliteImagery(
                farm_id       = farm_id,
                date_acquired = date.fromisoformat(imagery_meta.get('date', str(date.today()))),
                satellite     = satellite,
                cloud_cover   = imagery_meta.get('cloud_cover'),
                ndvi          = imagery_meta.get('ndvi'),
                evi           = imagery_meta.get('evi'),
                moisture_index= imagery_meta.get('moisture_index'),
                raw_data      = imagery_meta,
            )
            db.session.add(record)
            db.session.commit()

        return jsonify({
            'success':   True,
            'farm_id':   farm_id,
            'farm_name': farm.name,
            'satellite': satellite,
            'imagery':   imagery_meta,
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/satellite/farms/<id>/indices ────────────────────────────────────

@satellite_bp.route('/farms/<int:farm_id>/indices', methods=['GET'])
def get_farm_indices(farm_id):
    """
    Get All Spectral Indices in One Call (NDVI + EVI + Moisture)
    ---
    tags:
      - Satellite
    parameters:
      - name: farm_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: NDVI, EVI, and soil moisture index from GEE in one response
      404:
        description: Farm not found
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        geometry = _get_geometry(farm)
        if not geometry:
            return jsonify({'success': False, 'error': 'Farm has no spatial geometry'}), 400

        # Fetch all indices from GEE
        latest_ndvi  = gee.get_latest_ndvi(geometry)
        moisture_pct = gee.get_soil_moisture(geometry)

        ndvi_val = latest_ndvi['ndvi'] if latest_ndvi else None
        evi_val  = latest_ndvi.get('evi') if latest_ndvi else None

        health_score  = gee.calculate_health_score(ndvi_val) if ndvi_val else 0
        health_status = gee.get_health_status(health_score)
        moisture_status = gee.get_moisture_status(moisture_pct)

        # Save combined reading
        record = SatelliteImagery(
            farm_id        = farm_id,
            date_acquired  = date.today(),
            satellite      = 'sentinel-2',
            ndvi           = ndvi_val,
            evi            = evi_val,
            moisture_index = moisture_pct,
            raw_data       = {'ndvi': ndvi_val, 'evi': evi_val, 'moisture': moisture_pct},
        )
        db.session.add(record)
        db.session.commit()

        return jsonify({
            'success':   True,
            'farm_id':   farm_id,
            'farm_name': farm.name,
            'date':      str(date.today()),
            'source':    'Google Earth Engine / Sentinel-2',
            'indices': {
                'ndvi': {
                    'value':        ndvi_val,
                    'health_score': health_score,
                    'status':       health_status.get('status') if health_status else None,
                    'description':  health_status.get('description') if health_status else None,
                },
                'evi': {
                    'value':       evi_val,
                    'description': 'Enhanced Vegetation Index — less atmosphere-sensitive than NDVI',
                },
                'soil_moisture': {
                    'value':       moisture_pct,
                    'status':      moisture_status.get('status') if moisture_status else None,
                    'description': moisture_status.get('description') if moisture_status else None,
                },
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── POST /api/satellite/farms/<id>/refresh ───────────────────────────────────

@satellite_bp.route('/farms/<int:farm_id>/refresh', methods=['POST'])
def refresh_farm_data(farm_id):
    """
    Trigger Manual GEE Data Refresh for a Farm
    ---
    tags:
      - Satellite
    parameters:
      - name: farm_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Fresh data fetched and saved to DB
      404:
        description: Farm not found
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        geometry = _get_geometry(farm)
        if not geometry:
            return jsonify({'success': False, 'error': 'Farm has no spatial geometry'}), 400

        results = {}

        # 1. Refresh NDVI
        ndvi_series  = gee.get_ndvi_time_series(geometry, days=30)
        latest_ndvi  = ndvi_series[-1] if ndvi_series else None
        if latest_ndvi:
            health_score = gee.calculate_health_score(latest_ndvi['ndvi'])
            health_status = gee.get_health_status(health_score)
            db.session.add(NDVIReading(
                farm_id      = farm_id,
                date         = date.fromisoformat(latest_ndvi['date']),
                ndvi_value   = latest_ndvi['ndvi'],
                health_score = health_score,
                status       = health_status['status'] if health_status else None,
                source       = 'sentinel-2'
            ))
            results['ndvi'] = {'value': latest_ndvi['ndvi'], 'health_score': health_score}

        # 2. Refresh Moisture
        moisture_pct    = gee.get_soil_moisture(geometry)
        moisture_status = gee.get_moisture_status(moisture_pct)
        db.session.add(MoistureReading(
            farm_id          = farm_id,
            date             = date.today(),
            moisture_percent = moisture_pct,
            status           = moisture_status['status'] if moisture_status else None,
            days_since_rain  = 0
        ))
        results['moisture'] = {'value': moisture_pct, 'status': moisture_status.get('status')}

        # 3. Save combined imagery record
        db.session.add(SatelliteImagery(
            farm_id       = farm_id,
            date_acquired = date.today(),
            satellite     = 'sentinel-2',
            ndvi          = latest_ndvi['ndvi'] if latest_ndvi else None,
            moisture_index= moisture_pct,
            raw_data      = results,
        ))

        db.session.commit()

        return jsonify({
            'success':    True,
            'farm_id':    farm_id,
            'farm_name':  farm.name,
            'refreshed_at': datetime.utcnow().isoformat(),
            'results':    results,
            'message':    'Farm satellite data refreshed successfully',
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/satellite/farms/<id>/history ────────────────────────────────────

@satellite_bp.route('/farms/<int:farm_id>/history', methods=['GET'])
def get_satellite_history(farm_id):
    """
    Get Saved Satellite Imagery History from Database
    ---
    tags:
      - Satellite
    parameters:
      - name: farm_id
        in: path
        type: integer
        required: true
      - name: days
        in: query
        type: integer
        default: 90
      - name: satellite
        in: query
        type: string
        description: Filter by satellite (sentinel-2, landsat-8)
    responses:
      200:
        description: Historical satellite readings from DB
      404:
        description: Farm not found
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        days      = int(request.args.get('days', 90))
        satellite = request.args.get('satellite')
        since     = date.today() - timedelta(days=days)

        query = SatelliteImagery.query.filter(
            SatelliteImagery.farm_id == farm_id,
            SatelliteImagery.date_acquired >= since
        )
        if satellite:
            query = query.filter_by(satellite=satellite)

        records = query.order_by(SatelliteImagery.date_acquired.desc()).all()

        return jsonify({
            'success':   True,
            'farm_id':   farm_id,
            'farm_name': farm.name,
            'days':      days,
            'count':     len(records),
            'history':   [r.to_dict() for r in records],
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/satellite/coverage ──────────────────────────────────────────────

@satellite_bp.route('/coverage', methods=['GET'])
def get_coverage_summary():
    """
    Get Satellite Data Coverage Summary Across All Farms
    ---
    tags:
      - Satellite
    responses:
      200:
        description: How many farms have recent satellite data
    """
    try:
        total_farms   = Farm.query.filter_by(status='active').count()
        since_30_days = date.today() - timedelta(days=30)

        farms_with_data = db.session.query(
            SatelliteImagery.farm_id
        ).filter(
            SatelliteImagery.date_acquired >= since_30_days
        ).distinct().count()

        farms_without = total_farms - farms_with_data

        return jsonify({
            'success':           True,
            'total_farms':       total_farms,
            'farms_with_recent_data': farms_with_data,
            'farms_without_data': farms_without,
            'coverage_percent':  round((farms_with_data / total_farms * 100), 1) if total_farms else 0,
            'data_window_days':  30,
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500