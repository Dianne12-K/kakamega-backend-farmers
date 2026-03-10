"""
routes/farm_routes.py
----------------------
Farm endpoints — migrated from SQLite + raw Database() class
to SQLAlchemy + PostGIS models.
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from extensions import db
from core.models import Farm, NDVIReading, MoistureReading, Recommendation

farm_bp = Blueprint('farms', __name__)


# ── Helper ────────────────────────────────────────────────────────────────────

def get_latest_ndvi(farm_id):
    return (NDVIReading.query
            .filter_by(farm_id=farm_id)
            .order_by(NDVIReading.date.desc())
            .first())

def get_latest_moisture(farm_id):
    return (MoistureReading.query
            .filter_by(farm_id=farm_id)
            .order_by(MoistureReading.date.desc())
            .first())

def get_latest_recommendation(farm_id):
    return (Recommendation.query
            .filter_by(farm_id=farm_id, is_resolved=False)
            .order_by(Recommendation.created_at.desc())
            .first())

def enrich_farm(farm):
    """Attach latest health, moisture to a farm dict."""
    data = farm.to_dict()

    ndvi = get_latest_ndvi(farm.id)
    data['current_health'] = {
        'score':    ndvi.health_score,
        'status':   ndvi.status,
        'ndvi':     float(ndvi.ndvi_value) if ndvi.ndvi_value else None,
        'date':     str(ndvi.date),
        'source':   ndvi.source,
    } if ndvi else None

    moisture = get_latest_moisture(farm.id)
    data['current_moisture'] = {
        'percent':        float(moisture.moisture_percent) if moisture.moisture_percent else None,
        'status':         moisture.status,
        'days_since_rain': moisture.days_since_rain,
        'date':           str(moisture.date),
    } if moisture else None

    return data


# ── GET /api/farms  &  POST /api/farms ───────────────────────────────────────

@farm_bp.route('/', methods=['GET', 'POST'])
def farms():
    """
    Get All Farms or Create New Farm
    ---
    tags:
      - Farms
    parameters:
      - in: body
        name: body
        required: false
        schema:
          type: object
          properties:
            name:
              type: string
              example: Kakamega Test Farm
            crop_type:
              type: string
              example: maize
            planting_date:
              type: string
              format: date
              example: 2024-06-15
            area_ha:
              type: number
              example: 2.5
            latitude:
              type: number
              example: 0.2827
            longitude:
              type: number
              example: 34.7519
            ward_id:
              type: integer
              example: 1
    responses:
      200:
        description: List of farms (GET)
      201:
        description: Farm created (POST)
    """

    # ── GET ALL FARMS ─────────────────────────────────────────
    if request.method == 'GET':
        try:
            # Optional filters from query string
            crop_type = request.args.get('crop_type')
            status    = request.args.get('status', 'active')
            ward_id   = request.args.get('ward_id', type=int)

            query = Farm.query
            if status:
                query = query.filter_by(status=status)
            if crop_type:
                query = query.filter_by(crop_type=crop_type)
            if ward_id:
                query = query.filter_by(ward_id=ward_id)

            farms = query.order_by(Farm.created_at.desc()).all()

            return jsonify({
                'success': True,
                'count':   len(farms),
                'farms':   [enrich_farm(f) for f in farms]
            })

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ── CREATE FARM ───────────────────────────────────────────
    elif request.method == 'POST':
        try:
            data = request.get_json() or {}

            if not data.get('name') or not data.get('latitude') or not data.get('longitude'):
                return jsonify({
                    'success': False,
                    'error': 'Missing required fields: name, latitude, longitude'
                }), 400

            # Parse planting date if provided
            planting_date = None
            if data.get('planting_date'):
                try:
                    planting_date = datetime.strptime(data['planting_date'], '%Y-%m-%d').date()
                except ValueError:
                    return jsonify({'success': False, 'error': 'Invalid planting_date format. Use YYYY-MM-DD'}), 400

            farm = Farm(
                name                = data['name'],
                crop_type           = data.get('crop_type', 'maize'),
                planting_date       = planting_date,
                area_ha             = data.get('area_ha', 0),
                latitude            = data['latitude'],
                longitude           = data['longitude'],
                soil_type           = data.get('soil_type'),
                irrigation          = data.get('irrigation'),
                fertilizer_used     = data.get('fertilizer_used'),
                status              = data.get('status', 'active'),
                ward_id             = data.get('ward_id'),
            )

            db.session.add(farm)
            db.session.commit()
            # Note: PostGIS trigger auto-sets farm.location from lat/lon

            return jsonify({
                'success': True,
                'farm_id': farm.id,
                'message': 'Farm created successfully'
            }), 201

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 400


# ── GET /api/farms/<id> ───────────────────────────────────────────────────────

@farm_bp.route('/<int:farm_id>', methods=['GET'])
def get_farm(farm_id):
    """
    Get Farm Details
    ---
    tags:
      - Farms
    parameters:
      - name: farm_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Farm details with health, moisture, and NDVI history
      404:
        description: Farm not found
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        # NDVI history — last 90 days
        since = datetime.utcnow().date() - timedelta(days=90)
        ndvi_history = (NDVIReading.query
                        .filter_by(farm_id=farm_id)
                        .filter(NDVIReading.date >= since)
                        .order_by(NDVIReading.date.asc())
                        .all())

        latest_rec = get_latest_recommendation(farm_id)

        return jsonify({
            'success':              True,
            'farm':                 enrich_farm(farm),
            'latest_health':        get_latest_ndvi(farm_id).to_dict() if get_latest_ndvi(farm_id) else None,
            'latest_moisture':      get_latest_moisture(farm_id).to_dict() if get_latest_moisture(farm_id) else None,
            'latest_recommendation': latest_rec.to_dict() if latest_rec else None,
            'ndvi_history':         [n.to_dict() for n in ndvi_history],
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── PUT /api/farms/<id> ───────────────────────────────────────────────────────

@farm_bp.route('/<int:farm_id>', methods=['PUT'])
def update_farm(farm_id):
    """
    Update Farm Details
    ---
    tags:
      - Farms
    parameters:
      - name: farm_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        schema:
          type: object
    responses:
      200:
        description: Farm updated
      404:
        description: Farm not found
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        data = request.get_json() or {}

        # Update allowed fields
        updatable = ['name', 'crop_type', 'area_ha', 'soil_type',
                     'irrigation', 'fertilizer_used', 'status',
                     'yield_estimate_tons', 'ward_id']
        for field in updatable:
            if field in data:
                setattr(farm, field, data[field])

        # Update coordinates — trigger will update geometry
        if 'latitude' in data:
            farm.latitude = data['latitude']
        if 'longitude' in data:
            farm.longitude = data['longitude']

        if 'planting_date' in data and data['planting_date']:
            farm.planting_date = datetime.strptime(data['planting_date'], '%Y-%m-%d').date()

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Farm updated successfully',
            'farm':    farm.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


# ── DELETE /api/farms/<id> ────────────────────────────────────────────────────

@farm_bp.route('/<int:farm_id>', methods=['DELETE'])
def delete_farm(farm_id):
    """
    Delete a Farm
    ---
    tags:
      - Farms
    parameters:
      - name: farm_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Farm deleted
      404:
        description: Farm not found
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        db.session.delete(farm)
        db.session.commit()

        return jsonify({'success': True, 'message': f'Farm {farm_id} deleted'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/farms/<id>/geojson ───────────────────────────────────────────────

@farm_bp.route('/<int:farm_id>/geojson', methods=['GET'])
def get_farm_geojson(farm_id):
    """
    Get Farm as GeoJSON Feature
    ---
    tags:
      - Farms
    parameters:
      - name: farm_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: GeoJSON Feature with farm geometry
    """
    try:
        farm = Farm.query.get(farm_id)
        if not farm:
            return jsonify({'success': False, 'error': 'Farm not found'}), 404

        return jsonify(farm.to_geojson())

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/farms/geojson (all farms as FeatureCollection) ──────────────────

@farm_bp.route('/geojson', methods=['GET'])
def farms_geojson():
    """
    Get All Farms as GeoJSON FeatureCollection
    ---
    tags:
      - Farms
    responses:
      200:
        description: GeoJSON FeatureCollection — use directly in Leaflet/OpenLayers
    """
    try:
        farms = Farm.query.filter_by(status='active').all()
        return jsonify({
            'type':     'FeatureCollection',
            'features': [f.to_geojson() for f in farms]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500