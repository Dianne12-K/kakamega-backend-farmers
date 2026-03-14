"""
ml/
---
Machine learning module for the GeoAI Platform.

Models:
  - YieldPredictionModel     → RandomForestRegressor
  - PestRiskModel            → RandomForestClassifier
  - HealthForecastModel      → GradientBoostingRegressor
  - LandCoverModel           → RandomForestClassifier

Entry point:
  from ml.service import ml_service
  ml_service.init_app(app)   # called once in app factory
"""

from ml.service import ml_service

__all__ = ['ml_service']