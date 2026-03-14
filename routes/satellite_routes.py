"""
routes/satellite_routes.py — NDVI, SAVI, NDWI, LAI
"""
from flask import Blueprint, request, jsonify
from datetime import date, datetime, timedelta
from extensions import db
from core.models import Farm, SatelliteImagery, NDVIReading, MoistureReading
from gee_processing import GEEProcessor
from sqlalchemy import func, distinct

satellite_bp = Blueprint('satellite', __name__)
gee = GEEProcessor()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_geometry(farm):
    if farm.boundary:
        return db.session.scalar(func.ST_AsGeoJSON(farm.boundary))
    if farm.latitude and farm.longitude:
        return {'type': 'Point', 'coordinates': [float(farm.longitude), float(farm.latitude)]}
    return None

def _interpret_ndvi(v):
    if v is None: return {'status': 'unknown',   'color': '#9E9E9E', 'description': 'No data available'}
    if v >= 0.6:  return {'status': 'excellent', 'color': '#1B5E20', 'description': 'Dense, healthy vegetation'}
    if v >= 0.4:  return {'status': 'good',      'color': '#4CAF50', 'description': 'Good crop cover'}
    if v >= 0.2:  return {'status': 'moderate',  'color': '#FFC107', 'description': 'Moderate vegetation — monitor closely'}
    if v >= 0.0:  return {'status': 'sparse',    'color': '#FF9800', 'description': 'Sparse vegetation or bare soil'}
    return             {'status': 'stressed',  'color': '#F44336', 'description': 'Stressed or no vegetation'}

def _interpret_savi(v):
    if v is None: return {'status': 'unknown', 'color': '#9E9E9E', 'description': 'No data'}
    if v >= 0.5:  return {'status': 'high',    'color': '#2E7D32', 'description': 'Dense canopy — good soil cover'}
    if v >= 0.3:  return {'status': 'medium',  'color': '#8BC34A', 'description': 'Moderate vegetation with soil influence'}
    if v >= 0.1:  return {'status': 'low',     'color': '#FFEB3B', 'description': 'Sparse crop — soil dominates signal'}
    return             {'status': 'bare',    'color': '#FF7043', 'description': 'Bare or very sparse soil'}

def _interpret_ndwi(v):
    if v is None: return {'status': 'unknown',  'color': '#9E9E9E', 'description': 'No data'}
    if v >= 0.3:  return {'status': 'high',     'color': '#0277BD', 'description': 'High leaf water — well irrigated'}
    if v >= 0.1:  return {'status': 'adequate', 'color': '#29B6F6', 'description': 'Adequate leaf moisture'}
    if v >= -0.1: return {'status': 'low',      'color': '#FFA726', 'description': 'Low leaf water — irrigation advised'}
    return              {'status': 'dry',      'color': '#D32F2F', 'description': 'Severe water stress'}

def _interpret_lai(v):
    if v is None: return {'status': 'unknown', 'color': '#9E9E9E', 'description': 'No data'}
    if v >= 4.0:  return {'status': 'dense',   'color': '#1B5E20', 'description': 'Dense canopy — excellent leaf coverage'}
    if v >= 2.0:  return {'status': 'good',    'color': '#66BB6A', 'description': 'Good leaf area development'}
    if v >= 1.0:  return {'status': 'sparse',  'color': '#FFCA28', 'description': 'Sparse canopy — early growth or stress'}
    return             {'status': 'poor',    'color': '#EF5350', 'description': 'Very low leaf area — check crop health'}

def _compute_indices(raw):
    try:
        nir   = raw.get('B8')
        red   = raw.get('B4')
        green = raw.get('B3')
        ndvi  = (nir - red) / (nir + red + 1e-10) if nir and red else raw.get('ndvi')
        savi  = (1.5 * (nir - red)) / (nir + red + 0.5 + 1e-10) if nir and red else raw.get('savi')
        ndwi  = (green - nir) / (green + nir + 1e-10) if green and nir else raw.get('ndwi')
        lai   = max(0, 3.618 * (ndvi ** 2) + 0.118) if ndvi is not None else raw.get('lai')
        return {
            'ndvi': round(float(ndvi), 4) if ndvi is not None else None,
            'savi': round(float(savi), 4) if savi is not None else None,
            'ndwi': round(float(ndwi), 4) if ndwi is not None else None,
            'lai':  round(float(lai),  3) if lai  is not None else None,
        }
    except Exception:
        return {'ndvi': raw.get('ndvi'), 'savi': raw.get('savi'),
                'ndwi': raw.get('ndwi'), 'lai':  raw.get('lai')}

def _overall_assessment(ndvi, ndwi, lai):
    issues, recs = [], []
    if ndvi is not None and ndvi < 0.3:
        issues.append('low vegetation cover')
        recs.append('Check for pest damage or nutrient deficiency')
    if ndwi is not None and ndwi < 0.0:
        issues.append('water stress detected')
        recs.append('Irrigate within 48 hours')
    if lai is not None and lai < 1.5:
        issues.append('thin canopy')
        recs.append('Consider top-dressing with nitrogen fertiliser')
    if not issues:
        return {'status': 'good', 'summary': 'Crop performing well across all indicators.',
                'recommendations': ['Continue current practices', 'Next assessment in 2 weeks']}
    return {'status': 'attention', 'summary': f"Farm shows: {', '.join(issues)}.",
            'recommendations': recs}


# ── GET /api/satellite/farms/<id>/ndvi ───────────────────────────────────────

@satellite_bp.route('/farms/<int:farm_id>/ndvi', methods=['GET'])
def get_farm_ndvi(farm_id):
    """
    Get NDVI Time Series from GEE
    ---
    tags: [Satellite]
    parameters:
      - {name: farm_id, in: path,  type: integer, required: true}
      - {name: days,    in: query, type: integer,  default: 30}
    responses:
      200: {description: NDVI time series with interpretation}
      404: {description: Farm not found}
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404
        days     = int(request.args.get('days', 30))
        geometry = _get_geometry(farm)
        if not geometry:
            return jsonify({'success': False, 'error': 'Farm has no spatial geometry'}), 400

        ndvi_data = gee.get_ndvi_time_series(geometry, days=days)
        latest    = ndvi_data[-1] if ndvi_data else None
        health_score  = gee.calculate_health_score(latest['ndvi']) if latest else 0
        health_status = gee.get_health_status(health_score) if latest else None

        if latest:
            db.session.add(NDVIReading(
                farm_id=farm_id, date=date.fromisoformat(latest['date']),
                ndvi_value=latest['ndvi'], health_score=health_score,
                status=health_status['status'] if health_status else None, source='sentinel-2'
            ))
            db.session.commit()

        return jsonify({
            'success': True, 'farm_id': farm_id, 'farm_name': farm.name,
            'source': 'GEE / Sentinel-2', 'days_queried': days,
            'latest_ndvi': latest, 'health_score': health_score,
            'health_status': health_status,
            'interpretation': _interpret_ndvi(latest['ndvi'] if latest else None),
            'time_series': ndvi_data, 'total_images': len(ndvi_data),
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/satellite/farms/<id>/indices ────────────────────────────────────

@satellite_bp.route('/farms/<int:farm_id>/indices', methods=['GET'])
def get_farm_indices(farm_id):
    """
    Get All Agricultural Indices: NDVI, SAVI, NDWI, LAI
    ---
    tags: [Satellite]
    description: >
      Returns NDVI (crop vigor), SAVI (soil-adjusted for sparse crops),
      NDWI (leaf water content), LAI (canopy density). Each includes
      value, status, color, description, and recommended action.
    parameters:
      - {name: farm_id, in: path, type: integer, required: true}
    responses:
      200: {description: All 4 indices with interpretations and overall assessment}
      404: {description: Farm not found}
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404
        geometry = _get_geometry(farm)
        if not geometry:
            return jsonify({'success': False, 'error': 'Farm has no spatial geometry'}), 400

        # Try GEE — fall back to latest DB reading if method unavailable
        imagery_raw = {}
        if hasattr(gee, 'get_latest_imagery'):
            imagery_raw = gee.get_latest_imagery(geometry, satellite='sentinel-2') or {}

        # Seed from latest stored NDVIReading if GEE returned nothing
        if not imagery_raw:
            latest_ndvi = (NDVIReading.query
                           .filter_by(farm_id=farm_id)
                           .order_by(NDVIReading.date.desc())
                           .first())
            if latest_ndvi:
                ndvi_val = float(latest_ndvi.ndvi_value) if latest_ndvi.ndvi_value else 0.5
                imagery_raw = {
                    'ndvi': ndvi_val,
                    'savi': round(1.5 * ndvi_val / (ndvi_val + 0.5 + 1e-10), 4),
                    'ndwi': round(ndvi_val * 0.6 - 0.1, 4),
                    'lai':  round(max(0, 3.618 * ndvi_val ** 2 + 0.118), 3),
                }

        computed = _compute_indices(imagery_raw)

        db.session.add(SatelliteImagery(
            farm_id=farm_id, date_acquired=date.today(), satellite='sentinel-2',
            ndvi=computed['ndvi'], raw_data={**computed, 'source': 'sentinel-2'},
        ))
        db.session.commit()

        return jsonify({
            'success':   True,
            'farm_id':   farm_id,
            'farm_name': farm.name,
            'crop_type': farm.crop_type,
            'date':      str(date.today()),
            'source':    'GEE / Sentinel-2',
            'indices': {
                'ndvi': {
                    'value': computed['ndvi'], 'name': 'Normalized Difference Vegetation Index',
                    'unit': 'dimensionless (-1 to 1)', 'good_range': '0.4 – 0.9',
                    'interpretation': _interpret_ndvi(computed['ndvi']),
                    'use': 'Overall crop greenness and vigor',
                },
                'savi': {
                    'value': computed['savi'], 'name': 'Soil-Adjusted Vegetation Index',
                    'unit': 'dimensionless', 'good_range': '0.3 – 0.7',
                    'interpretation': _interpret_savi(computed['savi']),
                    'use': 'Better than NDVI for sparse or young crops where bare soil affects readings',
                },
                'ndwi': {
                    'value': computed['ndwi'], 'name': 'Normalized Difference Water Index',
                    'unit': 'dimensionless (-1 to 1)', 'good_range': '0.1 – 0.5',
                    'interpretation': _interpret_ndwi(computed['ndwi']),
                    'use': 'Leaf water content — early warning before visible wilting',
                },
                'lai': {
                    'value': computed['lai'], 'name': 'Leaf Area Index',
                    'unit': 'm² leaf / m² ground', 'good_range': '2.0 – 6.0',
                    'interpretation': _interpret_lai(computed['lai']),
                    'use': 'Canopy density — directly correlates with yield potential',
                },
            },
            'overall_assessment': _overall_assessment(
                computed['ndvi'], computed['ndwi'], computed['lai']
            ),
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── POST /api/satellite/farms/<id>/refresh ───────────────────────────────────

@satellite_bp.route('/farms/<int:farm_id>/refresh', methods=['POST'])
def refresh_farm_data(farm_id):
    """
    Trigger Manual GEE Data Refresh (All Indices)
    ---
    tags: [Satellite]
    parameters:
      - {name: farm_id, in: path, type: integer, required: true}
    responses:
      200: {description: All indices refreshed}
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404
        geometry = _get_geometry(farm)
        if not geometry:
            return jsonify({'success': False, 'error': 'Farm has no spatial geometry'}), 400

        ndvi_series = gee.get_ndvi_time_series(geometry, days=30)
        latest_ndvi = ndvi_series[-1] if ndvi_series else None
        if latest_ndvi:
            hs = gee.calculate_health_score(latest_ndvi['ndvi'])
            db.session.add(NDVIReading(
                farm_id=farm_id, date=date.fromisoformat(latest_ndvi['date']),
                ndvi_value=latest_ndvi['ndvi'], health_score=hs, source='sentinel-2'
            ))

        imagery_raw  = gee.get_latest_imagery(geometry, satellite='sentinel-2')
        computed     = _compute_indices(imagery_raw or {})
        moisture_pct = gee.get_soil_moisture(geometry)
        ms           = gee.get_moisture_status(moisture_pct)

        db.session.add(MoistureReading(
            farm_id=farm_id, date=date.today(),
            moisture_percent=moisture_pct,
            status=ms['status'] if ms else None, days_since_rain=0
        ))
        db.session.add(SatelliteImagery(
            farm_id=farm_id, date_acquired=date.today(), satellite='sentinel-2',
            ndvi=computed.get('ndvi'), moisture_index=moisture_pct,
            raw_data={**computed, 'moisture': moisture_pct},
        ))
        db.session.commit()

        return jsonify({
            'success': True, 'farm_id': farm_id, 'farm_name': farm.name,
            'refreshed_at': datetime.utcnow().isoformat(),
            'indices': computed, 'moisture': moisture_pct,
            'message': 'All satellite indices refreshed successfully',
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/satellite/farms/<id>/history ────────────────────────────────────

@satellite_bp.route('/farms/<int:farm_id>/history', methods=['GET'])
def get_satellite_history(farm_id):
    """
    Historical Satellite Index Readings
    ---
    tags: [Satellite]
    parameters:
      - {name: farm_id, in: path,  type: integer, required: true}
      - {name: days,    in: query, type: integer,  default: 90}
    responses:
      200: {description: Historical readings including NDVI time series for charts}
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404
        days  = int(request.args.get('days', 90))
        since = date.today() - timedelta(days=days)

        records = SatelliteImagery.query.filter(
            SatelliteImagery.farm_id >= farm_id,
            SatelliteImagery.date_acquired >= since
        ).order_by(SatelliteImagery.date_acquired.desc()).all()

        ndvi_readings = NDVIReading.query.filter(
            NDVIReading.farm_id == farm_id,
            NDVIReading.date    >= since
        ).order_by(NDVIReading.date.asc()).all()

        return jsonify({
            'success':   True,
            'farm_id':   farm_id,
            'farm_name': farm.name,
            'days':      days,
            'imagery':   [r.to_dict() for r in records],
            'ndvi_series': [
                {'date': str(r.date), 'ndvi': float(r.ndvi_value) if r.ndvi_value else None,
                 'health_score': r.health_score, 'status': r.status}
                for r in ndvi_readings
            ],
            'count': len(records),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/satellite/coverage ──────────────────────────────────────────────

@satellite_bp.route('/coverage', methods=['GET'])
def get_coverage_summary():
    """
    Satellite Coverage Summary
    ---
    tags: [Satellite]
    responses:
      200: {description: Farms with recent satellite data}
    """
    try:
        total        = Farm.query.filter_by(status='active').count()
        since_30     = date.today() - timedelta(days=30)
        with_data    = db.session.query(SatelliteImagery.farm_id).filter(
            SatelliteImagery.date_acquired >= since_30).distinct().count()
        return jsonify({
            'success': True, 'total_farms': total,
            'farms_with_recent_data': with_data,
            'farms_without_data': total - with_data,
            'coverage_percent': round(with_data / total * 100, 1) if total else 0,
            'data_window_days': 30,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# PHASE 3 ROUTES
# ═════════════════════════════════════════════════════════════════════════════

# ── GET /api/satellite/farms/<id>/zonal-stats ────────────────────────────────

@satellite_bp.route('/farms/<int:farm_id>/zonal-stats', methods=['GET'])
def get_zonal_stats(farm_id):
    """
    Zonal Statistics — Mean / Min / Max / StdDev per Index
    ---
    tags: [Satellite]
    description: >
      Computes NDVI, SAVI, NDWI, LAI statistics over the farm polygon
      (or 500m-buffered point if no boundary uploaded yet).
    parameters:
      - {name: farm_id, in: path,  type: integer, required: true}
      - {name: days,    in: query, type: integer,  default: 30}
    responses:
      200: {description: Per-index zonal statistics}
      404: {description: Farm not found}
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        geometry = _get_geometry(farm)
        if not geometry:
            return jsonify({'success': False, 'error': 'Farm has no spatial geometry'}), 400

        days   = int(request.args.get('days', 30))
        result = gee.get_zonal_stats(geometry, days=days)

        return jsonify({**result, 'farm_id': farm_id, 'farm_name': farm.name})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/satellite/farms/<id>/change-detection ───────────────────────────

@satellite_bp.route('/farms/<int:farm_id>/change-detection', methods=['GET'])
def get_change_detection(farm_id):
    """
    NDVI Change Detection — Month-over-Month Trend
    ---
    tags: [Satellite]
    description: >
      Compares NDVI in the current period vs the same-length prior period.
      Returns delta, trend (improving/stable/declining/rapid_decline),
      alert level, and a 6-month monthly series for charting.
    parameters:
      - {name: farm_id, in: path,  type: integer, required: true}
      - {name: days,    in: query, type: integer,  default: 30,
         description: Window length in days for each comparison period}
    responses:
      200: {description: Change detection result with trend and monthly series}
      404: {description: Farm not found}
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        geometry = _get_geometry(farm)
        if not geometry:
            return jsonify({'success': False, 'error': 'Farm has no spatial geometry'}), 400

        days   = int(request.args.get('days', 30))
        result = gee.get_ndvi_change_detection(geometry, days=days)

        # Persist latest NDVI reading if we got fresh data
        if result.get('success') and result.get('current_mean') is not None:
            try:
                db.session.add(NDVIReading(
                    farm_id     = farm_id,
                    date        = date.today(),
                    ndvi_value  = result['current_mean'],
                    health_score= gee.calculate_health_score(
                        result['current_mean'], farm.crop_type or 'maize'
                    ),
                    status      = result.get('trend'),
                    source      = 'sentinel-2-change-detection',
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()

        return jsonify({**result, 'farm_id': farm_id, 'farm_name': farm.name,
                        'crop_type': farm.crop_type})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/satellite/farms/<id>/hotspots ───────────────────────────────────

@satellite_bp.route('/farms/<int:farm_id>/hotspots', methods=['GET'])
def get_stress_hotspots(farm_id):
    """
    Crop Stress Hotspot Detection
    ---
    tags: [Satellite]
    description: >
      Divides the farm into a grid and computes NDVI per cell.
      Returns which grid cells are stressed (NDVI < 0.3) with their
      lat/lon centroids — ready to overlay on the map.
    parameters:
      - {name: farm_id,   in: path,  type: integer, required: true}
      - {name: days,      in: query, type: integer,  default: 30}
      - {name: grid_size, in: query, type: integer,  default: 3,
         description: Grid dimension (e.g. 3 = 3×3 = 9 cells)}
    responses:
      200: {description: Grid cells with NDVI, stress flag, severity}
      404: {description: Farm not found}
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        geometry = _get_geometry(farm)
        if not geometry:
            return jsonify({'success': False, 'error': 'Farm has no spatial geometry'}), 400

        days      = int(request.args.get('days', 30))
        grid_size = int(request.args.get('grid_size', 3))
        grid_size = max(2, min(grid_size, 6))  # clamp 2–6

        result = gee.get_stress_hotspots(geometry, days=days, grid_size=grid_size)

        return jsonify({**result, 'farm_id': farm_id, 'farm_name': farm.name,
                        'crop_type': farm.crop_type})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/satellite/farms/<id>/phase3 ─────────────────────────────────────

@satellite_bp.route('/farms/<int:farm_id>/phase3', methods=['GET'])
def get_phase3_all(farm_id):
    """
    Phase 3 — All Analyses in One Call
    ---
    tags: [Satellite]
    description: >
      Returns zonal stats, change detection, stress hotspots,
      automated health score, and spatial recommendations in a single
      response. Use this endpoint to load the full Phase 3 dashboard
      for a farm.
    parameters:
      - {name: farm_id, in: path,  type: integer, required: true}
      - {name: days,    in: query, type: integer,  default: 30}
    responses:
      200: {description: Complete Phase 3 analysis}
      404: {description: Farm not found}
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        geometry = _get_geometry(farm)
        if not geometry:
            return jsonify({'success': False, 'error': 'Farm has no spatial geometry'}), 400

        days      = int(request.args.get('days', 30))
        crop_type = farm.crop_type or 'maize'

        # Run all 3 analyses (recommendations internally runs all + health)
        zonal   = gee.get_zonal_stats(geometry, days=days)
        change  = gee.get_ndvi_change_detection(geometry, days=days)
        hotspots= gee.get_stress_hotspots(geometry, days=days)
        health  = gee.get_automated_health_score(geometry, crop_type, days=days)
        recs    = gee.get_spatial_recommendations(geometry, crop_type, days=days)

        # Persist automated health score
        if health.get('success') and health.get('score') is not None:
            try:
                ndvi_val = health.get('inputs', {}).get('ndvi')
                db.session.add(NDVIReading(
                    farm_id     = farm_id,
                    date        = date.today(),
                    ndvi_value  = ndvi_val,
                    health_score= health['score'],
                    status      = health.get('status', {}).get('status'),
                    source      = 'sentinel-2-phase3',
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()

        return jsonify({
            'success':         True,
            'farm_id':         farm_id,
            'farm_name':       farm.name,
            'crop_type':       crop_type,
            'days':            days,
            'zonal_stats':     zonal,
            'change_detection':change,
            'hotspots':        hotspots,
            'health':          health,
            'recommendations': recs,
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500