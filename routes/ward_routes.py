"""
routes/ward_routes.py
----------------------
Ward endpoints — migrated to SQLAlchemy + PostGIS.
"""
from flask import Blueprint, request, jsonify
from extensions import db
from core.models import Ward, Subcounty, Farm

ward_bp = Blueprint('wards', __name__)


@ward_bp.route('/', methods=['GET', 'POST'])
def wards():
    """
    Get All Wards or Create New Ward
    ---
    tags:
      - Wards
    parameters:
      - in: query
        name: subcounty_id
        type: integer
        description: Filter by sub-county
      - in: body
        name: body
        schema:
          type: object
          properties:
            name:
              type: string
              example: Butsotso East
            subcounty_id:
              type: integer
              example: 1
            code:
              type: string
            population:
              type: integer
            area_sq_km:
              type: number
    responses:
      200:
        description: List of wards (GET)
      201:
        description: Ward created (POST)
    """
    if request.method == 'GET':
        try:
            subcounty_id = request.args.get('subcounty_id', type=int)
            query = Ward.query
            if subcounty_id:
                query = query.filter_by(subcounty_id=subcounty_id)
            wards = query.order_by(Ward.name).all()

            result = []
            for w in wards:
                d = w.to_dict()
                d['subcounty_name'] = w.subcounty.name if w.subcounty else None
                d['farm_count']     = w.farms.count()
                result.append(d)

            return jsonify({'success': True, 'count': len(result), 'wards': result})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    elif request.method == 'POST':
        try:
            data = request.get_json() or {}
            if not data.get('name') or not data.get('subcounty_id'):
                return jsonify({'success': False, 'error': 'Missing required: name, subcounty_id'}), 400

            if not Subcounty.query.get(data['subcounty_id']):
                return jsonify({'success': False, 'error': 'Sub-county not found'}), 404

            ward = Ward(
                name         = data['name'],
                subcounty_id = data['subcounty_id'],
                code         = data.get('code', ''),
                population   = data.get('population', 0),
                area_sq_km   = data.get('area_sq_km', 0),
            )
            db.session.add(ward)
            db.session.commit()
            return jsonify({'success': True, 'ward_id': ward.id, 'message': 'Ward created'}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 400


@ward_bp.route('/<int:ward_id>', methods=['GET', 'PUT', 'DELETE'])
def ward_detail(ward_id):
    """
    Get, Update or Delete a Ward
    ---
    tags:
      - Wards
    parameters:
      - name: ward_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Ward data or updated
      404:
        description: Ward not found
    """
    ward = Ward.query.get(ward_id)
    if not ward:
        return jsonify({'success': False, 'error': 'Ward not found'}), 404

    if request.method == 'GET':
        try:
            data = ward.to_dict()
            data['subcounty']   = ward.subcounty.to_dict() if ward.subcounty else None
            data['farm_count']  = ward.farms.count()
            return jsonify({'success': True, 'ward': data})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    elif request.method == 'PUT':
        try:
            data = request.get_json() or {}
            if 'subcounty_id' in data and not Subcounty.query.get(data['subcounty_id']):
                return jsonify({'success': False, 'error': 'Sub-county not found'}), 404

            for field in ['name', 'subcounty_id', 'code', 'population', 'area_sq_km']:
                if field in data:
                    setattr(ward, field, data[field])
            db.session.commit()
            return jsonify({'success': True, 'message': 'Ward updated', 'ward': ward.to_dict()})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 400

    elif request.method == 'DELETE':
        try:
            db.session.delete(ward)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Ward deleted'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500


@ward_bp.route('/<int:ward_id>/farms', methods=['GET'])
def get_ward_farms(ward_id):
    """
    Get All Farms in a Ward
    ---
    tags:
      - Wards
    parameters:
      - name: ward_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Farms in this ward
      404:
        description: Ward not found
    """
    try:
        ward = Ward.query.get(ward_id)
        if not ward:
            return jsonify({'success': False, 'error': 'Ward not found'}), 404

        farms = Farm.query.filter_by(ward_id=ward_id, status='active').all()
        return jsonify({
            'success': True,
            'ward':    ward.name,
            'count':   len(farms),
            'farms':   [f.to_dict() for f in farms]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ward_bp.route('/<int:ward_id>/geojson', methods=['GET'])
def ward_geojson(ward_id):
    """
    Get Ward as GeoJSON Feature
    ---
    tags:
      - Wards
    parameters:
      - name: ward_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: GeoJSON Feature
    """
    try:
        ward = Ward.query.get(ward_id)
        if not ward:
            return jsonify({'success': False, 'error': 'Ward not found'}), 404
        return jsonify(ward.to_geojson())
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500