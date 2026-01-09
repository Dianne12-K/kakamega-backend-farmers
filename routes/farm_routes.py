from flask import Blueprint, request, jsonify
from database import Database

farm_bp = Blueprint('farms', __name__, url_prefix='/api')
db = Database()


@farm_bp.route('/farms', methods=['GET', 'POST'])
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
        description: Farm data for POST request
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
            boundary_geojson:
              type: object
    responses:
      200:
        description: List of farms (GET)
      201:
        description: Farm created (POST)
    """

    # =======================
    # GET ALL FARMS
    # =======================
    if request.method == 'GET':
        try:
            farms = db.get_all_farms()

            # Enrich farms with latest health & moisture data
            for farm in farms:
                farm_id = farm.get('id')

                # Latest NDVI / health
                ndvi_data = db.get_latest_ndvi(farm_id)
                if ndvi_data:
                    farm['current_health'] = {
                        'score': ndvi_data.get('health_score'),
                        'status': ndvi_data.get('status'),
                        'ndvi': ndvi_data.get('ndvi_value'),
                        'date': ndvi_data.get('date')
                    }
                else:
                    farm['current_health'] = None

                # Latest moisture
                moisture_data = db.get_latest_moisture(farm_id)
                if moisture_data:
                    farm['current_moisture'] = {
                        'percent': moisture_data.get('moisture_percent'),
                        'status': moisture_data.get('status'),
                        'days_since_rain': moisture_data.get('days_since_rain'),
                        'date': moisture_data.get('date')
                    }
                else:
                    farm['current_moisture'] = None

            return jsonify({
                'success': True,
                'count': len(farms),
                'farms': farms
            })

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # =======================
    # CREATE FARM
    # =======================
    elif request.method == 'POST':
        try:
            data = request.json or {}

            # Required fields validation
            if not data.get('name') or not data.get('latitude') or not data.get('longitude'):
                return jsonify({
                    'success': False,
                    'error': 'Missing required fields: name, latitude, longitude'
                }), 400

            farm_id = db.add_farm(
                name=data['name'],
                crop_type=data.get('crop_type', 'maize'),
                planting_date=data.get('planting_date'),
                area_ha=data.get('area_ha', 0),
                lat=data['latitude'],
                lon=data['longitude'],
                boundary_geojson=data.get('boundary_geojson', {})
            )

            return jsonify({
                'success': True,
                'farm_id': farm_id,
                'message': 'Farm created successfully'
            }), 201

        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 400


@farm_bp.route('/farms/<int:farm_id>', methods=['GET'])
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
        description: Farm details
      404:
        description: Farm not found
    """

    try:
        farm = db.get_farm(farm_id)

        if not farm:
            return jsonify({
                'success': False,
                'error': 'Farm not found'
            }), 404

        # Latest data
        latest_ndvi = db.get_latest_ndvi(farm_id)
        latest_moisture = db.get_latest_moisture(farm_id)
        latest_recommendation = db.get_recommendation(farm_id)

        # Attach formatted current health
        if latest_ndvi:
            farm['current_health'] = {
                'score': latest_ndvi.get('health_score'),
                'status': latest_ndvi.get('status'),
                'ndvi': latest_ndvi.get('ndvi_value'),
                'date': latest_ndvi.get('date')
            }
        else:
            farm['current_health'] = None

        # Attach formatted current moisture
        if latest_moisture:
            farm['current_moisture'] = {
                'percent': latest_moisture.get('moisture_percent'),
                'status': latest_moisture.get('status'),
                'days_since_rain': latest_moisture.get('days_since_rain'),
                'date': latest_moisture.get('date')
            }
        else:
            farm['current_moisture'] = None

        return jsonify({
            'success': True,
            'farm': farm,
            'latest_health': latest_ndvi,
            'latest_moisture': latest_moisture,
            'latest_recommendation': latest_recommendation,
            'ndvi_history': db.get_ndvi_history(farm_id, days=90)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
