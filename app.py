"""
app.py — GeoAI Platform App Factory
"""
from flask import Flask, jsonify
from config import config
from extensions import db, cors, SWAGGER_CONFIG, SWAGGER_TEMPLATE


def create_app(env='development'):
    app = Flask(__name__)
    app.config.from_object(config[env])

    # ── Init Extensions ───────────────────────────────────────
    db.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    app.config['SWAGGER'] = SWAGGER_CONFIG
    from flasgger import Swagger as _Swagger
    _Swagger(app, template=SWAGGER_TEMPLATE)

    # ── Register Blueprints ───────────────────────────────────
    from routes.health_routes          import health_bp
    from routes.farm_routes            import farm_bp
    from routes.weather_routes         import weather_bp
    from routes.market_routes          import market_bp
    from routes.recommendation_routes  import recommendation_bp
    from routes.subcounty_routes       import subcounty_bp
    from routes.ward_routes            import ward_bp
    from routes.satellite_routes       import satellite_bp
    from routes.spatial_routes         import spatial_bp
    from routes.analytics_routes       import analytics_bp
    from routes.ml_routes              import ml_bp
    from routes.boundary_routes        import boundary_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(farm_bp,           url_prefix='/api/farms')
    app.register_blueprint(weather_bp,        url_prefix='/api/weather')
    app.register_blueprint(market_bp,         url_prefix='/api/markets')
    app.register_blueprint(recommendation_bp, url_prefix='/api/recommendations')
    app.register_blueprint(subcounty_bp,      url_prefix='/api/subcounties')
    app.register_blueprint(ward_bp,           url_prefix='/api/wards')
    app.register_blueprint(satellite_bp,      url_prefix='/api/satellite')
    app.register_blueprint(spatial_bp,        url_prefix='/api/spatial')
    app.register_blueprint(analytics_bp,      url_prefix='/api/analytics')
    app.register_blueprint(ml_bp,             url_prefix='/api/ml')
    app.register_blueprint(boundary_bp,       url_prefix='/api/boundaries')

    # ── Create DB Tables ──────────────────────────────────────
    with app.app_context():
        db.create_all()

    # ── Boot ML models (load from disk or train) ──────────────
    from ml.service import ml_service
    ml_service.init_app(app)

    # ── Root ──────────────────────────────────────────────────
    @app.route('/')
    def index():
        return jsonify({
            "name":          "Kakamega Smart Farm — GeoAI Platform",
            "version":       "3.0.0",
            "status":        "online",
            "documentation": "/docs",
            "database":      "PostgreSQL + PostGIS",
            "endpoints": {
                "farms":           "/api/farms",
                "weather":         "/api/weather",
                "markets":         "/api/markets",
                "recommendations": "/api/recommendations",
                "subcounties":     "/api/subcounties",
                "wards":           "/api/wards",
                "satellite":       "/api/satellite",
                "spatial":         "/api/spatial",
                "analytics":       "/api/analytics",
                "ml":              "/api/ml",
                "boundaries":      "/api/boundaries",
                "docs":            "/docs",
            }
        })

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Resource not found", "status": 404}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error", "status": 500}), 500

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "status": 400}), 400

    return app


if __name__ == '__main__':
    app = create_app('development')
    app.run(host='0.0.0.0', port=5000, debug=True)