from flask import Blueprint, request, jsonify
from database import Database

ward_bp = Blueprint('wards', __name__, url_prefix='/api')
db = Database()


@ward_bp.route('/wards', methods=['GET', 'POST'])
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
        required: false
        description: Filter wards by sub-county ID
      - in: body
        name: body
        required: false
        description: Ward data for POST request
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
              example: BSE
            population:
              type: integer
              example: 15000
            area_sq_km:
              type: number
              example: 25.5
    responses:
      200:
        description: List of wards (GET)
      201:
        description: Ward created (POST)
    """

    # =======================
    # GET ALL WARDS
    # =======================
    if request.method == 'GET':
        try:
            subcounty_id = request.args.get('subcounty_id', type=int)

            if subcounty_id:
                wards = db.get_wards_by_subcounty(subcounty_id)
            else:
                wards = db.get_all_wards()

            # Enrich with sub-county name
            for ward in wards:
                if ward.get('subcounty_id'):
                    subcounty = db.get_subcounty(ward['subcounty_id'])
                    ward['subcounty_name'] = subcounty['name'] if subcounty else None

            return jsonify({
                'success': True,
                'count': len(wards),
                'wards': wards
            })

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # =======================
    # CREATE WARD
    # =======================
    elif request.method == 'POST':
        try:
            data = request.json or {}

            # Required fields validation
            if not data.get('name') or not data.get('subcounty_id'):
                return jsonify({
                    'success': False,
                    'error': 'Missing required fields: name, subcounty_id'
                }), 400

            # Verify sub-county exists
            subcounty = db.get_subcounty(data['subcounty_id'])
            if not subcounty:
                return jsonify({
                    'success': False,
                    'error': 'Sub-county not found'
                }), 404

            ward_id = db.add_ward(
                name=data['name'],
                subcounty_id=data['subcounty_id'],
                code=data.get('code', ''),
                population=data.get('population', 0),
                area_sq_km=data.get('area_sq_km', 0)
            )

            return jsonify({
                'success': True,
                'ward_id': ward_id,
                'message': 'Ward created successfully'
            }), 201

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400


@ward_bp.route('/wards/<int:ward_id>', methods=['GET', 'PUT', 'DELETE'])
def ward_detail(ward_id):
    """
    Get, Update or Delete Ward
    ---
    tags:
      - Wards
    parameters:
      - name: ward_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        required: false
        description: Ward data for PUT request
        schema:
          type: object
          properties:
            name:
              type: string
            subcounty_id:
              type: integer
            code:
              type: string
            population:
              type: integer
            area_sq_km:
              type: number
    responses:
      200:
        description: Ward details or updated
      204:
        description: Ward deleted
      404:
        description: Ward not found
    """

    # =======================
    # GET WARD
    # =======================
    if request.method == 'GET':
        try:
            ward = db.get_ward(ward_id)

            if not ward:
                return jsonify({
                    'success': False,
                    'error': 'Ward not found'
                }), 404

            # Get sub-county details
            if ward.get('subcounty_id'):
                subcounty = db.get_subcounty(ward['subcounty_id'])
                ward['subcounty'] = subcounty

            return jsonify({
                'success': True,
                'ward': ward
            })

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # =======================
    # UPDATE WARD
    # =======================
    elif request.method == 'PUT':
        try:
            # Check if exists
            ward = db.get_ward(ward_id)
            if not ward:
                return jsonify({
                    'success': False,
                    'error': 'Ward not found'
                }), 404

            data = request.json or {}

            # If updating subcounty_id, verify it exists
            if data.get('subcounty_id'):
                subcounty = db.get_subcounty(data['subcounty_id'])
                if not subcounty:
                    return jsonify({
                        'success': False,
                        'error': 'Sub-county not found'
                    }), 404

            # Update ward
            success = db.update_ward(
                ward_id=ward_id,
                name=data.get('name'),
                subcounty_id=data.get('subcounty_id'),
                code=data.get('code'),
                population=data.get('population'),
                area_sq_km=data.get('area_sq_km')
            )

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Ward updated successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to update ward'
                }), 400

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400

    # =======================
    # DELETE WARD
    # =======================
    elif request.method == 'DELETE':
        try:
            # Check if exists
            ward = db.get_ward(ward_id)
            if not ward:
                return jsonify({
                    'success': False,
                    'error': 'Ward not found'
                }), 404

            # Delete ward
            success = db.delete_ward(ward_id)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Ward deleted successfully'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to delete ward'
                }), 400

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


@ward_bp.route('/wards/<int:ward_id>/farms', methods=['GET'])
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
        description: List of farms in ward
      404:
        description: Ward not found
    """

    try:
        # Check if ward exists
        ward = db.get_ward(ward_id)
        if not ward:
            return jsonify({
                'success': False,
                'error': 'Ward not found'
            }), 404

        farms = db.get_farms_by_ward(ward_id)

        return jsonify({
            'success': True,
            'ward': ward['name'],
            'count': len(farms),
            'farms': farms
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500