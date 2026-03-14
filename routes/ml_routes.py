"""
routes/ml_routes.py
-------------------
ML prediction endpoints:

  POST /api/ml/yield/<farm_id>
  POST /api/ml/pest-risk/<farm_id>
  POST /api/ml/health-forecast/<farm_id>
  POST /api/ml/land-cover
  GET  /api/ml/farm/<farm_id>/all
  GET  /api/ml/status
  POST /api/ml/retrain
"""

from flask import Blueprint, jsonify, request, current_app
from ml.service import ml_service

ml_bp = Blueprint('ml', __name__)


def _ok(data, farm_id=None):
    payload = {'success': True, 'data': data}
    if farm_id:
        payload['farm_id'] = farm_id
    return jsonify(payload)


def _err(msg, code=400):
    return jsonify({'success': False, 'error': msg}), code


# ── 1. Yield Prediction ───────────────────────────────────────
@ml_bp.route('/yield/<int:farm_id>', methods=['GET', 'POST'])
def yield_prediction(farm_id):
    """
    Predict expected crop yield for a farm.
    Uses: NDVI, health score, moisture, area, crop type, soil, irrigation.
    ---
    tags: [ML]
    parameters:
      - name: farm_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Yield prediction result
    """
    try:
        result = ml_service.predict_yield(farm_id)
        return _ok(result, farm_id)
    except Exception as e:
        return _err(str(e), 500)


# ── 2. Pest & Disease Risk ─────────────────────────────────────
@ml_bp.route('/pest-risk/<int:farm_id>', methods=['GET', 'POST'])
def pest_risk(farm_id):
    """
    Classify pest and disease risk level for a farm.
    Levels: low | medium | high | critical
    ---
    tags: [ML]
    parameters:
      - name: farm_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Pest risk classification
    """
    try:
        result = ml_service.predict_pest_risk(farm_id)
        return _ok(result, farm_id)
    except Exception as e:
        return _err(str(e), 500)


# ── 3. Crop Health Forecast ────────────────────────────────────
@ml_bp.route('/health-forecast/<int:farm_id>', methods=['GET', 'POST'])
def health_forecast(farm_id):
    """
    Forecast crop health score 14 days ahead.
    Uses: current health, NDVI trend, moisture, weather conditions.
    ---
    tags: [ML]
    parameters:
      - name: farm_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: 14-day health forecast
    """
    try:
        result = ml_service.predict_health_forecast(farm_id)
        return _ok(result, farm_id)
    except Exception as e:
        return _err(str(e), 500)


# ── 4. Land Cover Classification ──────────────────────────────
@ml_bp.route('/land-cover', methods=['POST'])
def land_cover():
    """
    Classify land cover type from spectral indices.
    ---
    tags: [ML]
    parameters:
      - in: body
        name: body
        schema:
          properties:
            ndvi:             { type: number, example: 0.62 }
            savi:             { type: number, example: 0.45 }
            ndwi:             { type: number, example: 0.12 }
            lai:              { type: number, example: 2.1  }
            health_score:     { type: number, example: 70   }
            moisture_percent: { type: number, example: 55   }
            latitude:         { type: number, example: 0.28 }
            longitude:        { type: number, example: 34.75}
    responses:
      200:
        description: Land cover classification result
    """
    try:
        payload = request.get_json(silent=True) or {}
        if not payload:
            return _err('Request body with spectral indices required')

        required = ['ndvi']
        missing  = [f for f in required if f not in payload]
        if missing:
            return _err(f'Missing required fields: {missing}')

        result = ml_service.classify_land_cover(payload)
        return _ok(result)
    except Exception as e:
        return _err(str(e), 500)


# ── 5. All predictions for one farm ───────────────────────────
@ml_bp.route('/farm/<int:farm_id>/all', methods=['GET'])
def farm_all_predictions(farm_id):
    """
    Run yield + pest risk + health forecast for a farm in one request.
    ---
    tags: [ML]
    parameters:
      - name: farm_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: All ML predictions for the farm
    """
    try:
        result = ml_service.predict_all(farm_id)
        return _ok(result, farm_id)
    except Exception as e:
        return _err(str(e), 500)


# ── 6. Model status ────────────────────────────────────────────
@ml_bp.route('/status', methods=['GET'])
def model_status():
    """
    Return training status and performance metrics for all models.
    ---
    tags: [ML]
    responses:
      200:
        description: ML model status
    """
    return jsonify({'success': True, 'models': ml_service.status})


# ── 7. Retrain ─────────────────────────────────────────────────
@ml_bp.route('/retrain', methods=['POST'])
def retrain():
    """
    Force retrain all models with latest DB data.
    Use after bulk data import or at end of growing season.
    ---
    tags: [ML]
    responses:
      200:
        description: Retraining metrics
    """
    try:
        metrics = ml_service.retrain_all(current_app._get_current_object())
        return jsonify({'success': True, 'metrics': metrics})
    except Exception as e:
        return _err(str(e), 500)