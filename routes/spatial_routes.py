"""
routes/spatial_routes.py
-------------------------
Spatial query endpoints powered by PostGIS.
Nearby farms, boundary queries, full map overview.
"""
from flask import Blueprint, request, jsonify
from extensions import db
from core.models import Farm, Market, CollectionCenter, Subcounty, Ward
from sqlalchemy import text, func

spatial_bp = Blueprint('spatial', __name__)


# ── GET /api/spatial/farms/nearby ────────────────────────────────────────────

@spatial_bp.route('/farms/nearby', methods=['GET'])
def farms_nearby():
    """
    Get Farms Within X km of a Point
    ---
    tags:
      - Spatial
    parameters:
      - name: lat
        in: query
        type: number
        required: true
        example: 0.2827
      - name: lon
        in: query
        type: number
        required: true
        example: 34.7519
      - name: km
        in: query
        type: number
        default: 10
        description: Search radius in kilometres
      - name: crop_type
        in: query
        type: string
        description: Optional crop filter
    responses:
      200:
        description: Farms within radius, sorted by distance
      400:
        description: Missing lat/lon
    """
    try:
        lat = request.args.get('lat', type=float)
        lon = request.args.get('lon', type=float)
        km  = request.args.get('km',  type=float, default=10)
        crop_type = request.args.get('crop_type')

        if lat is None or lon is None:
            return jsonify({'success': False, 'error': 'lat and lon are required'}), 400

        # PostGIS ST_DWithin (distance in metres)
        radius_m = km * 1000
        query = db.session.execute(text("""
                                        SELECT
                                            f.id, f.name, f.crop_type, f.area_ha, f.status,
                                            f.latitude, f.longitude, f.ward_id,
                                            ROUND(
                                                    ST_Distance(
                                                            f.location::geography,
                                                            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                                                    )::numeric / 1000, 2
                                            ) AS distance_km
                                        FROM farms f
                                        WHERE f.location IS NOT NULL
                                          AND f.status = 'active'
                                          AND ST_DWithin(
                                                f.location::geography,
                                                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                                                :radius_m
                                              )
                                          AND (:crop_type IS NULL OR f.crop_type = :crop_type)
                                        ORDER BY distance_km ASC
                                        """), {'lat': lat, 'lon': lon, 'radius_m': radius_m, 'crop_type': crop_type})

        rows = [dict(r._mapping) for r in query]

        return jsonify({
            'success':       True,
            'center':        {'latitude': lat, 'longitude': lon},
            'radius_km':     km,
            'count':         len(rows),
            'farms':         rows,
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/spatial/farms/within-subcounty/<id> ─────────────────────────────

@spatial_bp.route('/farms/within-subcounty/<int:subcounty_id>', methods=['GET'])
def farms_within_subcounty(subcounty_id):
    """
    Get All Farms Spatially Within a Subcounty Boundary
    ---
    tags:
      - Spatial
    parameters:
      - name: subcounty_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Farms whose location falls inside the subcounty polygon
      404:
        description: Subcounty not found or has no boundary
    """
    try:
        subcounty = Subcounty.query.get(subcounty_id)
        if not subcounty:
            return jsonify({'success': False, 'error': 'Subcounty not found'}), 404
        if not subcounty.geom:
            return jsonify({'success': False, 'error': 'Subcounty has no boundary geometry. Upload a shapefile first.'}), 400

        result = db.session.execute(text("""
                                         SELECT
                                             f.id, f.name, f.crop_type, f.area_ha,
                                             f.latitude, f.longitude, f.status
                                         FROM farms f
                                                  JOIN subcounties s ON s.id = :subcounty_id
                                         WHERE f.location IS NOT NULL
                                           AND ST_Within(f.location, s.geom)
                                         ORDER BY f.name
                                         """), {'subcounty_id': subcounty_id})

        rows = [dict(r._mapping) for r in result]

        return jsonify({
            'success':       True,
            'subcounty':     subcounty.name,
            'subcounty_id':  subcounty_id,
            'count':         len(rows),
            'farms':         rows,
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/spatial/markets/nearby ──────────────────────────────────────────

@spatial_bp.route('/markets/nearby', methods=['GET'])
def markets_nearby():
    """
    Get Nearest Markets and Collection Centers to a Location
    ---
    tags:
      - Spatial
    parameters:
      - name: lat
        in: query
        type: number
        required: true
      - name: lon
        in: query
        type: number
        required: true
      - name: km
        in: query
        type: number
        default: 25
      - name: type
        in: query
        type: string
        description: "market | collection_center | all (default: all)"
    responses:
      200:
        description: Nearby markets and collection centers with distances
    """
    try:
        lat      = request.args.get('lat', type=float)
        lon      = request.args.get('lon', type=float)
        km       = request.args.get('km',  type=float, default=25)
        typ      = request.args.get('type', 'all')
        radius_m = km * 1000

        if lat is None or lon is None:
            return jsonify({'success': False, 'error': 'lat and lon are required'}), 400

        markets = []
        centers = []

        if typ in ('market', 'all'):
            result = db.session.execute(text("""
                                             SELECT
                                                 m.id, m.name, m.location_text AS location,
                                                 m.contact_phone, m.operating_days,
                                                 m.latitude, m.longitude,
                                                 ROUND(
                                                         ST_Distance(
                                                                 m.location::geography,
                                                                 ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                                                         )::numeric / 1000, 2
                                                 ) AS distance_km
                                             FROM markets m
                                             WHERE m.location IS NOT NULL
                                               AND m.is_active = true
                                               AND ST_DWithin(
                                                     m.location::geography,
                                                     ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                                                     :radius_m
                                                   )
                                             ORDER BY distance_km ASC
                                                 LIMIT 10
                                             """), {'lat': lat, 'lon': lon, 'radius_m': radius_m})
            markets = [dict(r._mapping) for r in result]

        if typ in ('collection_center', 'all'):
            result = db.session.execute(text("""
                                             SELECT
                                                 cc.id, cc.name, cc.location_text AS location,
                                                 cc.crops_accepted, cc.contact_phone,
                                                 cc.latitude, cc.longitude,
                                                 ROUND(
                                                         ST_Distance(
                                                                 cc.location::geography,
                                                                 ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                                                         )::numeric / 1000, 2
                                                 ) AS distance_km
                                             FROM collection_centers cc
                                             WHERE cc.location IS NOT NULL
                                               AND cc.is_active = true
                                               AND ST_DWithin(
                                                     cc.location::geography,
                                                     ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                                                     :radius_m
                                                   )
                                             ORDER BY distance_km ASC
                                                 LIMIT 10
                                             """), {'lat': lat, 'lon': lon, 'radius_m': radius_m})
            centers = [dict(r._mapping) for r in result]

        return jsonify({
            'success':            True,
            'center':             {'latitude': lat, 'longitude': lon},
            'radius_km':          km,
            'markets':            markets,
            'collection_centers': centers,
            'total_found':        len(markets) + len(centers),
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── GET /api/spatial/overview ─────────────────────────────────────────────────

@spatial_bp.route('/overview', methods=['GET'])
def spatial_overview():
    """
    Full Map Snapshot — All Layers at Once
    ---
    tags:
      - Spatial
    description: >
      Returns all active farms, markets, collection centers, subcounties and wards
      as a single GeoJSON FeatureCollection per layer. Use this to load the
      complete map in one API call from the Vue.js frontend.
    responses:
      200:
        description: All spatial layers as GeoJSON FeatureCollections
    """
    try:
        # Farms
        farms = Farm.query.filter_by(status='active').all()
        farm_features = []
        for f in farms:
            geom = f.boundary or f.location
            if geom:
                geojson_geom = db.session.scalar(func.ST_AsGeoJSON(geom))
                farm_features.append({
                    'type': 'Feature',
                    'geometry': __import__('json').loads(geojson_geom) if geojson_geom else None,
                    'properties': {
                        'id':        f.id,
                        'name':      f.name,
                        'crop_type': f.crop_type,
                        'area_ha':   float(f.area_ha) if f.area_ha else None,
                        'status':    f.status,
                        'layer':     'farms',
                    }
                })

        # Markets
        markets = Market.query.filter_by(is_active=True).all()
        market_features = []
        for m in markets:
            if m.location:
                geojson_geom = db.session.scalar(func.ST_AsGeoJSON(m.location))
                market_features.append({
                    'type': 'Feature',
                    'geometry': __import__('json').loads(geojson_geom) if geojson_geom else None,
                    'properties': {
                        'id':       m.id,
                        'name':     m.name,
                        'location': m.location_text,
                        'phone':    m.contact_phone,
                        'layer':    'markets',
                    }
                })

        # Collection Centers
        centers = CollectionCenter.query.filter_by(is_active=True).all()
        center_features = []
        for c in centers:
            if c.location:
                geojson_geom = db.session.scalar(func.ST_AsGeoJSON(c.location))
                center_features.append({
                    'type': 'Feature',
                    'geometry': __import__('json').loads(geojson_geom) if geojson_geom else None,
                    'properties': {
                        'id':              c.id,
                        'name':            c.name,
                        'crops_accepted':  c.crops_accepted,
                        'storage_capacity': c.storage_capacity,
                        'layer':           'collection_centers',
                    }
                })

        # Subcounty boundaries
        subcounties = Subcounty.query.all()
        subcounty_features = []
        for s in subcounties:
            if s.geom:
                geojson_geom = db.session.scalar(func.ST_AsGeoJSON(s.geom))
                subcounty_features.append({
                    'type': 'Feature',
                    'geometry': __import__('json').loads(geojson_geom) if geojson_geom else None,
                    'properties': {
                        'id':   s.id,
                        'name': s.name,
                        'code': s.code,
                        'layer': 'subcounties',
                    }
                })

        return jsonify({
            'success': True,
            'layers': {
                'farms': {
                    'type':     'FeatureCollection',
                    'count':    len(farm_features),
                    'features': farm_features,
                },
                'markets': {
                    'type':     'FeatureCollection',
                    'count':    len(market_features),
                    'features': market_features,
                },
                'collection_centers': {
                    'type':     'FeatureCollection',
                    'count':    len(center_features),
                    'features': center_features,
                },
                'subcounties': {
                    'type':     'FeatureCollection',
                    'count':    len(subcounty_features),
                    'features': subcounty_features,
                },
            },
            'summary': {
                'total_farms':              len(farm_features),
                'total_markets':            len(market_features),
                'total_collection_centers': len(center_features),
                'total_subcounties':        len(subcounty_features),
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500