
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

# SQLAlchemy instance — imported by all models
db = SQLAlchemy()

# CORS instance
cors = CORS()


SWAGGER_TEMPLATE = {
    "info": {
        "title": "Kakamega Smart Farm — GeoAI Platform API",
        "description": (
            "A modular AI-powered geospatial intelligence API for Kakamega County. "
            "Covers farms, weather, markets, satellite imagery (GEE), and ML-based "
            "recommendations. Built with Flask + PostGIS."
        ),
        "version": "3.0.0",
        "contact": {
            "name": "GeoAI Platform",
        }
    },
    "schemes": ["http", "https"],
    "tags": [
        {"name": "Health",           "description": "API health check"},
        {"name": "Farms",            "description": "Farm management & spatial queries"},
        {"name": "Weather",          "description": "Weather data & forecasts"},
        {"name": "Markets",          "description": "Market prices & collection centers"},
        {"name": "Recommendations",  "description": "AI-generated farm recommendations"},
        {"name": "Subcounties",      "description": "Kakamega subcounty boundaries"},
        {"name": "Wards",            "description": "Ward boundaries & demographics"},
        {"name": "Satellite",        "description": "GEE satellite imagery & NDVI"},
    ]
}

SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint":     "apispec",
            "route":        "/apispec.json",
            "rule_filter":  lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui":       True,
    "specs_route":      "/docs"
}