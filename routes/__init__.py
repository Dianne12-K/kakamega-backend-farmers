# This file makes the routes directory a Python package
# You can leave it empty or add route imports here

from .farm_routes import farm_bp
from .health_routes import health_bp
from .weather_routes import weather_bp
from .recommendation_routes import recommendation_bp

__all__ = ['farm_bp', 'health_bp', 'weather_bp', 'recommendation_bp']