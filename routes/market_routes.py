"""
routes/market_routes.py
------------------------
Markets, prices & collection centers — migrated to SQLAlchemy + PostGIS.
"""
from flask import Blueprint, request, jsonify
from datetime import date
from extensions import db
from core.models import Market, MarketPrice, CollectionCenter
from sqlalchemy import func, text

market_bp = Blueprint('markets', __name__)


# ── Markets ───────────────────────────────────────────────────────────────────

@market_bp.route('/', methods=['GET'])
def get_markets():
    """
    Get all markets
    ---
    tags:
      - Markets
    parameters:
      - name: active_only
        in: query
        type: string
        default: "true"
    responses:
      200:
        description: List of markets
    """
    try:
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        query = Market.query
        if active_only:
            query = query.filter_by(is_active=True)
        markets = query.order_by(Market.name).all()
        return jsonify({'success': True, 'count': len(markets), 'markets': [m.to_dict() for m in markets]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/', methods=['POST'])
def create_market():
    """
    Create a new market
    ---
    tags:
      - Markets
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - name
          properties:
            name:
              type: string
            location:
              type: string
            latitude:
              type: number
              example: 0.2827
            longitude:
              type: number
              example: 34.7519
            contact_phone:
              type: string
            contact_person:
              type: string
            operating_days:
              type: string
            payment_terms:
              type: string
    responses:
      201:
        description: Market created
      400:
        description: Invalid input
    """
    try:
        data = request.get_json() or {}
        if not data.get('name'):
            return jsonify({'success': False, 'error': 'Market name is required'}), 400

        market = Market(
            name           = data['name'],
            location_text  = data.get('location'),
            latitude       = data.get('latitude'),
            longitude      = data.get('longitude'),
            contact_phone  = data.get('contact_phone'),
            contact_person = data.get('contact_person'),
            operating_days = data.get('operating_days'),
            payment_terms  = data.get('payment_terms'),
            is_active      = True,
        )
        db.session.add(market)
        db.session.commit()
        return jsonify({'success': True, 'market_id': market.id, 'message': 'Market created successfully'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@market_bp.route('/<int:market_id>', methods=['GET'])
def get_market(market_id):
    """
    Get a specific market with its current prices
    ---
    tags:
      - Markets
    parameters:
      - name: market_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Market details
      404:
        description: Market not found
    """
    try:
        market = Market.query.get(market_id)
        if not market:
            return jsonify({'success': False, 'error': 'Market not found'}), 404

        data = market.to_dict()
        data['current_prices'] = [
            p.to_dict() for p in
            MarketPrice.query.filter_by(market_id=market_id, is_current=True).all()
        ]
        return jsonify({'success': True, 'market': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/<int:market_id>', methods=['PUT'])
def update_market(market_id):
    """
    Update a market
    ---
    tags:
      - Markets
    parameters:
      - name: market_id
        in: path
        type: integer
        required: true
      - name: body
        in: body
        schema:
          type: object
    responses:
      200:
        description: Market updated
    """
    try:
        market = Market.query.get(market_id)
        if not market:
            return jsonify({'success': False, 'error': 'Market not found'}), 404

        data = request.get_json() or {}
        for field in ['name', 'location_text', 'contact_phone', 'contact_person',
                      'operating_days', 'payment_terms', 'is_active', 'latitude', 'longitude']:
            if field in data:
                setattr(market, field, data[field])
        # keep 'location' key as alias for location_text
        if 'location' in data:
            market.location_text = data['location']

        db.session.commit()
        return jsonify({'success': True, 'message': 'Market updated', 'market': market.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@market_bp.route('/<int:market_id>', methods=['DELETE'])
def delete_market(market_id):
    """
    Deactivate a market (soft delete)
    ---
    tags:
      - Markets
    parameters:
      - name: market_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Market deactivated
    """
    try:
        market = Market.query.get(market_id)
        if not market:
            return jsonify({'success': False, 'error': 'Market not found'}), 404
        market.is_active = False
        db.session.commit()
        return jsonify({'success': True, 'message': f'Market {market_id} deactivated'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


# ── Market Prices ─────────────────────────────────────────────────────────────

@market_bp.route('/prices', methods=['POST'])
def create_price():
    """
    Create a new market price entry
    ---
    tags:
      - Markets
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - market_id
            - crop_type
            - price
          properties:
            market_id:
              type: integer
            crop_type:
              type: string
            price:
              type: number
            unit:
              type: string
            grade:
              type: string
            notes:
              type: string
    responses:
      201:
        description: Price created
    """
    try:
        data = request.get_json() or {}
        required = ['market_id', 'crop_type', 'price']
        if not all(k in data for k in required):
            return jsonify({'success': False, 'error': f'Missing required fields: {required}'}), 400

        # Mark previous prices for same crop+market as not current
        MarketPrice.query.filter_by(
            market_id=data['market_id'],
            crop_type=data['crop_type'],
            is_current=True
        ).update({'is_current': False})

        price = MarketPrice(
            market_id     = data['market_id'],
            crop_type     = data['crop_type'],
            price         = data['price'],
            unit          = data.get('unit', 'per 90kg bag'),
            grade         = data.get('grade'),
            date_recorded = date.today(),
            is_current    = True,
            notes         = data.get('notes'),
        )
        db.session.add(price)
        db.session.commit()
        return jsonify({'success': True, 'price_id': price.id, 'message': 'Price recorded'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400


@market_bp.route('/prices/<crop_type>', methods=['GET'])
def get_prices(crop_type):
    """
    Get current prices for a crop across all markets
    ---
    tags:
      - Markets
    parameters:
      - name: crop_type
        in: path
        type: string
        required: true
        description: e.g. maize, beans, sugarcane
      - name: current_only
        in: query
        type: string
        default: "true"
    responses:
      200:
        description: Prices for the crop
      404:
        description: No prices found
    """
    try:
        current_only = request.args.get('current_only', 'true').lower() == 'true'
        query = MarketPrice.query.filter_by(crop_type=crop_type.lower())
        if current_only:
            query = query.filter_by(is_current=True)

        prices = query.order_by(MarketPrice.price.asc()).all()
        if not prices:
            return jsonify({'success': False, 'error': f'No prices found for {crop_type}'}), 404

        # Enrich with market names
        result = []
        for p in prices:
            d = p.to_dict()
            d['market_name'] = p.market.name if p.market else None
            d['market_location'] = p.market.location_text if p.market else None
            result.append(d)

        return jsonify({
            'success':   True,
            'crop_type': crop_type,
            'count':     len(result),
            'prices':    result,
            'summary': {
                'min_price': min(p['price'] for p in result),
                'max_price': max(p['price'] for p in result),
                'avg_price': round(sum(p['price'] for p in result) / len(result), 2),
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Collection Centers ────────────────────────────────────────────────────────

@market_bp.route('/collection-centers', methods=['GET'])
def get_centers():
    """
    Get all collection centers, optionally filtered by crop and sorted by distance
    ---
    tags:
      - Markets
    parameters:
      - name: crop_type
        in: query
        type: string
      - name: active_only
        in: query
        type: string
        default: "true"
      - name: lat
        in: query
        type: number
        description: Your latitude — centers sorted by distance
      - name: lon
        in: query
        type: number
        description: Your longitude
    responses:
      200:
        description: List of collection centers
    """
    try:
        crop_type   = request.args.get('crop_type')
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        lat         = request.args.get('lat', type=float)
        lon         = request.args.get('lon', type=float)

        query = CollectionCenter.query
        if active_only:
            query = query.filter_by(is_active=True)
        if crop_type:
            query = query.filter(CollectionCenter.crops_accepted.ilike(f'%{crop_type}%'))

        centers = query.all()
        result  = [c.to_dict() for c in centers]

        # ── PostGIS distance sort if lat/lon provided ──────────
        if lat and lon and centers:
            # Add distance_km to each center using PostGIS ST_Distance
            for i, center in enumerate(centers):
                if center.latitude and center.longitude:
                    dist = db.session.scalar(
                        text("""
                            SELECT ST_Distance(
                                ST_SetSRID(ST_MakePoint(:clon, :clat), 4326)::geography,
                                ST_SetSRID(ST_MakePoint(:ulon, :ulat), 4326)::geography
                            ) / 1000
                        """),
                        {'clat': float(center.latitude), 'clon': float(center.longitude),
                         'ulat': lat, 'ulon': lon}
                    )
                    result[i]['distance_km'] = round(dist, 2) if dist else None
                else:
                    result[i]['distance_km'] = None

            result.sort(key=lambda x: x.get('distance_km') or 9999)

        return jsonify({'success': True, 'count': len(result), 'collection_centers': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@market_bp.route('/collection-centers', methods=['POST'])
def create_center():
    """
    Add a new collection center
    ---
    tags:
      - Markets
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - name
          properties:
            name:
              type: string
            location:
              type: string
            latitude:
              type: number
            longitude:
              type: number
            crops_accepted:
              type: string
            contact_phone:
              type: string
            operating_days:
              type: string
            storage_capacity:
              type: string
    responses:
      201:
        description: Collection center created
    """
    try:
        data = request.get_json() or {}
        if not data.get('name'):
            return jsonify({'success': False, 'error': 'Name is required'}), 400

        center = CollectionCenter(
            name                 = data['name'],
            location_text        = data.get('location'),
            latitude             = data.get('latitude'),
            longitude            = data.get('longitude'),
            crops_accepted       = data.get('crops_accepted'),
            contact_phone        = data.get('contact_phone'),
            contact_person       = data.get('contact_person'),
            operating_days       = data.get('operating_days'),
            operating_hours      = data.get('operating_hours'),
            storage_capacity     = data.get('storage_capacity'),
            payment_terms        = data.get('payment_terms'),
            minimum_quantity     = data.get('minimum_quantity'),
            quality_requirements = data.get('quality_requirements'),
            is_active            = True,
        )
        db.session.add(center)
        db.session.commit()
        return jsonify({'success': True, 'center_id': center.id, 'message': 'Collection center created'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400