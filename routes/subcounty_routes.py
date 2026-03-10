"""
routes/subcounty_routes.py
---------------------------
Subcounty endpoints — migrated to SQLAlchemy + PostGIS.
"""
from flask import Blueprint, request, jsonify
from extensions import db
from core.models import Subcounty, Ward, Farm

subcounty_bp = Blueprint('subcounties', __name__)


@subcounty_bp.route('/', methods=['GET', 'POST'])
def subcounties():
    """
    Get All Sub-Counties or Create New
    ---
    tags:
      - Subcounties
    parameters:
      - in: body
        name: body
        schema:
          type: object
          properties:
            name:
              type: string
              example: Butere
            code:
              type: string
              example: BTR
            description:
              type: string
    responses:
      200:
        description: List of sub-counties (GET)
      201:
        description: Sub-county created (POST)
    """
    if request.method == 'GET':
        try:
            subcounties = Subcounty.query.order_by(Subcounty.name).all()
            result = []
            for s in subcounties:
                d = s.to_dict()
                d['ward_count'] = s.wards.count()
                result.append(d)
            return jsonify({'success': True, 'count': len(result), 'subcounties': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    elif request.method == 'POST':
        try:
            data = request.get_json() or {}
            if not data.get('name'):
                return jsonify({'success': False, 'error': 'Missing required field: name'}), 400

            subcounty = Subcounty(
                name        = data['name'],
                code        = data.get('code', ''),
                description = data.get('description', ''),
            )
            db.session.add(subcounty)
            db.session.commit()
            return jsonify({'success': True, 'subcounty_id': subcounty.id, 'message': 'Sub-county created'}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 400


@subcounty_bp.route('/<int:subcounty_id>', methods=['GET', 'PUT', 'DELETE'])
def subcounty_detail(subcounty_id):
    """
    Get, Update or Delete a Sub-County
    ---
    tags:
      - Subcounties
    parameters:
      - name: subcounty_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Sub-county data or updated
      404:
        description: Not found
    """
    subcounty = Subcounty.query.get(subcounty_id)
    if not subcounty:
        return jsonify({'success': False, 'error': 'Sub-county not found'}), 404

    if request.method == 'GET':
        try:
            data = subcounty.to_dict()
            data['wards']      = [w.to_dict() for w in subcounty.wards.order_by(Ward.name).all()]
            data['ward_count'] = len(data['wards'])
            return jsonify({'success': True, 'subcounty': data})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    elif request.method == 'PUT':
        try:
            data = request.get_json() or {}
            for field in ['name', 'code', 'description']:
                if field in data:
                    setattr(subcounty, field, data[field])
            db.session.commit()
            return jsonify({'success': True, 'message': 'Sub-county updated', 'subcounty': subcounty.to_dict()})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 400

    elif request.method == 'DELETE':
        try:
            db.session.delete(subcounty)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Sub-county deleted'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500


@subcounty_bp.route('/<int:subcounty_id>/wards', methods=['GET'])
def get_subcounty_wards(subcounty_id):
    """
    Get All Wards in a Sub-County
    ---
    tags:
      - Subcounties
    parameters:
      - name: subcounty_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Wards list
      404:
        description: Sub-county not found
    """
    try:
        subcounty = Subcounty.query.get(subcounty_id)
        if not subcounty:
            return jsonify({'success': False, 'error': 'Sub-county not found'}), 404

        wards = subcounty.wards.order_by(Ward.name).all()
        return jsonify({
            'success':      True,
            'subcounty':    subcounty.name,
            'count':        len(wards),
            'wards':        [w.to_dict() for w in wards]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@subcounty_bp.route('/<int:subcounty_id>/geojson', methods=['GET'])
def subcounty_geojson(subcounty_id):
    """
    Get Sub-County as GeoJSON Feature
    ---
    tags:
      - Subcounties
    parameters:
      - name: subcounty_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: GeoJSON Feature
    """
    try:
        subcounty = Subcounty.query.get(subcounty_id)
        if not subcounty:
            return jsonify({'success': False, 'error': 'Sub-county not found'}), 404
        return jsonify(subcounty.to_geojson())
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@subcounty_bp.route('/geojson', methods=['GET'])
def all_subcounties_geojson():
    """
    Get All Sub-Counties as GeoJSON FeatureCollection
    ---
    tags:
      - Subcounties
    responses:
      200:
        description: GeoJSON FeatureCollection — use in Leaflet/OpenLayers
    """
    try:
        subcounties = Subcounty.query.all()
        return jsonify({
            'type':     'FeatureCollection',
            'features': [s.to_geojson() for s in subcounties]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500