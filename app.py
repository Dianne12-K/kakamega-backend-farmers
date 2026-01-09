from flask import Flask
from flask_cors import CORS
from flasgger import Swagger
from config import Config

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Swagger Configuration
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/apispec.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs"
}

swagger_template = {
    "info": {
        "title": "Kakamega Farms Smart Monitoring API",
        "description": "API for monitoring crop health, soil moisture, weather, and smart farming recommendations",
        "version": "1.0.0",
        "contact": {
            "name": "Kakamega Farms",
            "email": "info@kakamegafarms.ke"
        }
    },
    "host": "127.0.0.1:5000",
    "basePath": "/",
    "schemes": ["http"],
    "tags": [
        {"name": "System", "description": "System health and info"},
        {"name": "Farms", "description": "Farm management"},
        {"name": "Sub-Counties", "description": "Sub-county management"},
        {"name": "Wards", "description": "Ward management"},
        {"name": "Health", "description": "Crop health monitoring"},
        {"name": "Weather", "description": "Weather forecast"},
        {"name": "Recommendations", "description": "Smart farming recommendations"}
    ]
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

# Import and register blueprints (routes)
from routes.farm_routes import farm_bp
from routes.health_routes import health_bp
from routes.weather_routes import weather_bp
from routes.recommendation_routes import recommendation_bp
from routes.subcounty_routes import subcounty_bp
from routes.ward_routes import ward_bp

app.register_blueprint(farm_bp)
app.register_blueprint(health_bp)
app.register_blueprint(weather_bp)
app.register_blueprint(recommendation_bp)
app.register_blueprint(subcounty_bp)
app.register_blueprint(ward_bp)

# Home route
@app.route('/')
def home():
    """
    API Health Check
    ---
    tags:
      - System
    responses:
      200:
        description: API status and endpoints
    """
    return {
        'status': 'running',
        'message': 'Kakamega Farms Smart Monitoring API',
        'version': '1.0.0',
        'documentation': '/api/docs',
        'endpoints': {
            'farms': '/api/farms',
            'farm_detail': '/api/farms/<id>',
            'subcounties': '/api/subcounties',
            'subcounty_detail': '/api/subcounties/<id>',
            'wards': '/api/wards',
            'ward_detail': '/api/wards/<id>',
            'health': '/api/farms/<id>/health',
            'moisture': '/api/farms/<id>/moisture',
            'weather': '/api/weather',
            'recommendation': '/api/farms/<id>/recommendation',
            'irrigation': '/api/farms/<id>/irrigation-schedule'
        }
    }

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return {'success': False, 'error': 'Endpoint not found'}, 404

@app.errorhandler(500)
def internal_error(error):
    return {'success': False, 'error': 'Internal server error'}, 500

# Run app
if __name__ == '__main__':
    print("=" * 60)
    print(" KAKAMEGA FARMS SMART MONITORING SYSTEM")
    print("=" * 60)
    print(f" Default Location: {Config.DEFAULT_LAT}, {Config.DEFAULT_LON}")
    print(f"  Database: {Config.DATABASE_PATH}")
    print(f"  Weather API: {'✓ Configured' if Config.OPENWEATHER_API_KEY else '✗ NOT CONFIGURED'}")
    print(f"  Earth Engine: {'✓ Configured' if Config.GEE_PROJECT_ID else '✗ NOT CONFIGURED'}")
    print(f" API Documentation: http://127.0.0.1:5000/api/docs")
    print("=" * 60)
    print(" New Endpoints Available:")
    print("   • Sub-Counties: /api/subcounties")
    print("   • Wards: /api/wards")
    print("=" * 60)
    print(" Starting server...")
    print("=" * 60)

    app.run(debug=True, host='0.0.0.0', port=5000)