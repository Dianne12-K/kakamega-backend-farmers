"""
ml/service.py
-------------
Singleton service that owns all four ML models.
Called once at app startup via init_ml(app).
After that, any route can import `ml_service` and call predict methods.
"""

import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)


class MLService:
    def __init__(self):
        self.yield_model    = None
        self.pest_model     = None
        self.forecast_model = None
        self.land_model     = None
        self._trained       = False

    # ── Boot ──────────────────────────────────────────────────
    def init_app(self, app):
        """Load or train all models. Called from app factory."""
        from ml.models import (
            YieldPredictionModel, PestRiskModel,
            HealthForecastModel, LandCoverModel,
        )
        self.yield_model    = YieldPredictionModel()
        self.pest_model     = PestRiskModel()
        self.forecast_model = HealthForecastModel()
        self.land_model     = LandCoverModel()

        with app.app_context():
            db_rows = self._fetch_training_rows()

        for name, model in [
            ('yield',    self.yield_model),
            ('pest',     self.pest_model),
            ('forecast', self.forecast_model),
            ('land',     self.land_model),
        ]:
            if not model.load():
                logger.info(f'[ML] Training {name} model...')
                metric = model.train(db_rows)
                logger.info(f'[ML] {name} trained — metric={metric}')
            else:
                logger.info(f'[ML] {name} model loaded from disk')

        self._trained = True

    def retrain_all(self, app):
        """Force retrain all models (e.g. after bulk data import)."""
        with app.app_context():
            db_rows = self._fetch_training_rows()
        results = {}
        for name, model in [
            ('yield',    self.yield_model),
            ('pest',     self.pest_model),
            ('forecast', self.forecast_model),
        ]:
            metric = model.train(db_rows)
            results[name] = metric
        results['land_cover'] = self.land_model.train()
        return results

    # ── Training data builder ─────────────────────────────────
    def _fetch_training_rows(self):
        """
        Join farms + latest NDVI + latest moisture + latest weather
        into flat dicts suitable for feature extraction.
        """
        from core.models import Farm, NDVIReading, MoistureReading, WeatherData
        from extensions import db
        from sqlalchemy import func

        rows = []
        try:
            farms = Farm.query.filter_by(status='active').all()
            for farm in farms:
                # Latest NDVI
                ndvi = (NDVIReading.query
                        .filter_by(farm_id=farm.id)
                        .order_by(NDVIReading.date.desc())
                        .first())
                # Latest moisture
                moist = (MoistureReading.query
                         .filter_by(farm_id=farm.id)
                         .order_by(MoistureReading.date.desc())
                         .first())
                # Nearest weather (by lat/lon proximity, last 7 days)
                weather = (WeatherData.query
                           .filter(WeatherData.date >= date.today() - timedelta(days=7))
                           .order_by(
                    func.abs(WeatherData.latitude  - float(farm.latitude  or 0.28)) +
                    func.abs(WeatherData.longitude - float(farm.longitude or 34.75))
                )
                           .first())

                # Health trend: diff between latest and 3-readings-ago
                ndvi_readings = (NDVIReading.query
                                 .filter_by(farm_id=farm.id)
                                 .order_by(NDVIReading.date.desc())
                                 .limit(4).all())
                health_trend = 0.0
                if len(ndvi_readings) >= 2:
                    health_trend = float(
                        (ndvi_readings[0].health_score or 0) -
                        (ndvi_readings[-1].health_score or 0)
                    )

                days_since_planting = (
                    (date.today() - farm.planting_date).days
                    if farm.planting_date else 60
                )

                rows.append({
                    # Farm
                    'farm_id':              farm.id,
                    'crop_type':            farm.crop_type,
                    'area_ha':              float(farm.area_ha or 2.0),
                    'soil_type':            farm.soil_type,
                    'irrigation':           farm.irrigation,
                    'yield_estimate_tons':  float(farm.yield_estimate_tons or 0),
                    'planting_date':        farm.planting_date,
                    'latitude':             float(farm.latitude  or 0.28),
                    'longitude':            float(farm.longitude or 34.75),
                    'days_since_planting':  days_since_planting,
                    # NDVI / health
                    'ndvi_value':   float(ndvi.ndvi_value   if ndvi else 0.5),
                    'health_score': float(ndvi.health_score if ndvi else 50),
                    'health_trend': health_trend,
                    # Moisture
                    'moisture_percent': float(moist.moisture_percent if moist else 45),
                    'days_since_rain':  float(moist.days_since_rain  if moist else 5),
                    # Weather
                    'temperature': float(weather.temperature    if weather else 25),
                    'humidity':    float(weather.humidity        if weather else 70),
                    'rainfall_mm': float(weather.rain_amount     if weather else 5),
                })
        except Exception as e:
            logger.warning(f'[ML] DB fetch error — using empty rows: {e}')

        logger.info(f'[ML] Fetched {len(rows)} training rows from DB')
        return rows

    # ── Prediction helpers ────────────────────────────────────
    def predict_yield(self, farm_id):
        row = self._build_farm_row(farm_id)
        return self.yield_model.predict(row)

    def predict_pest_risk(self, farm_id):
        row = self._build_farm_row(farm_id)
        return self.pest_model.predict(row)

    def predict_health_forecast(self, farm_id):
        row = self._build_farm_row(farm_id)
        return self.forecast_model.predict(row)

    def classify_land_cover(self, payload):
        """payload is a dict of spectral indices from the request body."""
        return self.land_model.predict(payload)

    def predict_all(self, farm_id):
        """Run all three farm-level models in one call."""
        row = self._build_farm_row(farm_id)
        return {
            'yield':          self.yield_model.predict(row),
            'pest_risk':      self.pest_model.predict(row),
            'health_forecast': self.forecast_model.predict(row),
        }

    def _build_farm_row(self, farm_id):
        from core.models import Farm, NDVIReading, MoistureReading, WeatherData
        from sqlalchemy import func

        farm  = Farm.query.get_or_404(farm_id)
        ndvi  = (NDVIReading.query
                 .filter_by(farm_id=farm_id)
                 .order_by(NDVIReading.date.desc()).first())
        moist = (MoistureReading.query
                 .filter_by(farm_id=farm_id)
                 .order_by(MoistureReading.date.desc()).first())
        weather = (WeatherData.query
                   .filter(WeatherData.date >= date.today() - timedelta(days=7))
                   .order_by(
            func.abs(WeatherData.latitude  - float(farm.latitude  or 0.28)) +
            func.abs(WeatherData.longitude - float(farm.longitude or 34.75))
        ).first())

        ndvi_readings = (NDVIReading.query
                         .filter_by(farm_id=farm_id)
                         .order_by(NDVIReading.date.desc())
                         .limit(4).all())
        health_trend = 0.0
        if len(ndvi_readings) >= 2:
            health_trend = float(
                (ndvi_readings[0].health_score or 0) -
                (ndvi_readings[-1].health_score or 0)
            )

        return {
            'farm_id':             farm.id,
            'crop_type':           farm.crop_type,
            'area_ha':             float(farm.area_ha or 2.0),
            'soil_type':           farm.soil_type,
            'irrigation':          farm.irrigation,
            'yield_estimate_tons': float(farm.yield_estimate_tons or 0),
            'planting_date':       farm.planting_date,
            'latitude':            float(farm.latitude  or 0.28),
            'longitude':           float(farm.longitude or 34.75),
            'days_since_planting': (
                (date.today() - farm.planting_date).days
                if farm.planting_date else 60
            ),
            'ndvi_value':          float(ndvi.ndvi_value   if ndvi else 0.5),
            'health_score':        float(ndvi.health_score if ndvi else 50),
            'health_trend':        health_trend,
            'moisture_percent':    float(moist.moisture_percent if moist else 45),
            'days_since_rain':     float(moist.days_since_rain  if moist else 5),
            'temperature':         float(weather.temperature    if weather else 25),
            'humidity':            float(weather.humidity       if weather else 70),
            'rainfall_mm':         float(weather.rain_amount    if weather else 5),
        }

    @property
    def status(self):
        return {
            'trained':       self._trained,
            'yield_mae':     getattr(self.yield_model,    'mae',      None),
            'pest_accuracy': getattr(self.pest_model,     'accuracy', None),
            'forecast_mae':  getattr(self.forecast_model, 'mae',      None),
            'land_accuracy': getattr(self.land_model,     'accuracy', None),
        }


# Singleton — imported by routes
ml_service = MLService()