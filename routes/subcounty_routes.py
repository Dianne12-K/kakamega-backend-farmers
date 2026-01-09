from flask import Blueprint, request, jsonify
from database import Database

subcounty_bp = Blueprint('subcounties', __name__, url_prefix='/api')
db = Database()


@subcounty_bp.route('/subcounties', methods=['GET', 'POST'])
def subcounties():
    """
    Get All Sub-Counties or Create New Sub-County
    ---
    tags:
      - Sub-Counties
    parameters:
      - in: body
        name: body
        required: false
        description: Sub-county data for POST request
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
              example: Butere Sub-County in Kakamega County
    responses:
      200:
        description: List of sub-counties (GET)
      201:
        description: Sub-county created (POST)
    """

    # =======================
    # GET ALL SUB-COUNTIES
    # =======================
    if request.method == 'GET':
        try:
            subcounties = db.get_all_subcounties()

            # Enrich with ward count
            for subcounty in subcounties:
                subcounty_id = subcounty.get('id')
                ward_count = db.get_ward_count_by_subcounty(subcounty_id)
                subcounty['ward_count'] = ward_count

            return jsonify({
                'success': True,
                'count': len(subcounties),
                'subcounties': subcounties
            })

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # =======================
    # CREATE SUB-COUNTY
    # =======================
    elif request.method == 'POST':
        try:
            data = request.json or {}

            # Required fields validation
            if not data.get('name'):
                return jsonify({
                    'success': False,
                    'error': 'Missing required field: name'
                }), 400

            subcounty_id = db.add_subcounty(
                name=data['name'],
                code=data.get('code', ''),
                description=data.get('description', '')
            )

            return jsonify({
                'success': True,
                'subcounty_id': subcounty_id,
                'message': 'Sub-county created successfully'
            }), 201

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400


@subcounty_bp.route('/subcounties/<int:subcounty_id>', methods=['GET', 'PUT', 'DELETE'])
def subcounty_detail(subcounty_id):
    """
    Get, Update or Delete Sub-County
    ---
    tags:
      - Sub-Counties
    parameters:
      - name: subcounty_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        required: false
        description: Sub-county data for PUT request
        schema:
          type: object
          properties:
            name:
              type: string
            code:
              type: string
            description:
              type: string
    responses:
      200:
        description: Sub-county details or updated
      204:
        description: Sub-county deleted
      404:
        description: Sub-county not found
    """

    # =======================
    # GET SUB-COUNTY
    # =======================
    if request.method == 'GET':
        try:
            subcounty = db.get_subcounty(subcounty_id)

            if not subcounty:
                return jsonify({
                    'success': False,
                    'error': 'Sub-county not found'
                }), 404

            # Get associated wards
            wards = db.get_wards_by_subcounty(subcounty_id)
            subcounty['wards'] = wards
            subcounty['ward_count'] = len(wards)

            return jsonify({
                'success': True,
                'subcounty': subcounty
            })

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # =======================
    # UPDATE SUB-COUNTY
    # =======================
    elif request.method == 'PUT':
        try:
            # Check if exists
            subcounty = db.get_subcounty(subcounty_id)
            if not subcounty:
                return jsonify({
                    'success': False,
                    'error': 'Sub-county not found'
                }), 404

            data = request.json or {}

            # Update sub-county
            success = db.update_subcounty(
                subcounty_id=subcounty_id,
                name=data.get('name'),
                code=data.get('code'),
                description=data.get('description')
            )

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Sub-county updated successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to update sub-county'
                }), 400

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400

    # =======================
    # DELETE SUB-COUNTY
    # =======================
    elif request.method == 'DELETE':
        try:
            # Check if exists
            subcounty = db.get_subcounty(subcounty_id)
            if not subcounty:
                return jsonify({
                    'success': False,
                    'error': 'Sub-county not found'
                }), 404

            # Delete sub-county
            success = db.delete_subcounty(subcounty_id)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Sub-county deleted successfully'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to delete sub-county'
                }), 400

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


@subcounty_bp.route('/subcounties/<int:subcounty_id>/wards', methods=['GET'])
def get_subcounty_wards(subcounty_id):
    """
    Get All Wards in a Sub-County
    ---
    tags:
      - Sub-Counties
    parameters:
      - name: subcounty_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: List of wards in sub-county
      404:
        description: Sub-county not found
    """

    try:
        # Check if sub-county exists
        subcounty = db.get_subcounty(subcounty_id)
        if not subcounty:
            return jsonify({
                'success': False,
                'error': 'Sub-county not found'
            }), 404

        wards = db.get_wards_by_subcounty(subcounty_id)

        return jsonify({
            'success': True,
            'subcounty': subcounty['name'],
            'count': len(wards),
            'wards': wards
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500