"""
ml/models.py
------------
Four scikit-learn models for Kakamega Smart Farm:
  1. Yield Prediction       — RandomForestRegressor
  2. Pest & Disease Risk    — RandomForestClassifier
  3. Crop Health Forecast   — GradientBoostingRegressor
  4. Land Cover Classification — RandomForestClassifier

Each model class:
  - builds training data from the DB
  - trains itself if no saved model exists
  - exposes a predict() method
  - saves/loads itself from disk (joblib)
"""

import os
import numpy as np
import pandas as pd
import joblib
from datetime import date, timedelta
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, accuracy_score

# ── Model storage directory ───────────────────────────────────
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'saved_models')
os.makedirs(MODEL_DIR, exist_ok=True)


# ── Crop yield benchmarks (tons/ha) — Kenya agricultural data ─
CROP_YIELD_BENCHMARKS = {
    'maize':      { 'min': 1.5,  'max': 6.0,  'optimal_ndvi': 0.65 },
    'sugarcane':  { 'min': 40.0, 'max': 120.0, 'optimal_ndvi': 0.70 },
    'tea':        { 'min': 1.5,  'max': 4.0,   'optimal_ndvi': 0.72 },
    'beans':      { 'min': 0.8,  'max': 2.5,   'optimal_ndvi': 0.60 },
    'sorghum':    { 'min': 1.0,  'max': 4.0,   'optimal_ndvi': 0.58 },
    'cassava':    { 'min': 8.0,  'max': 25.0,  'optimal_ndvi': 0.62 },
    'vegetables': { 'min': 5.0,  'max': 20.0,  'optimal_ndvi': 0.68 },
    'sunflower':  { 'min': 0.8,  'max': 2.5,   'optimal_ndvi': 0.60 },
}

CROP_TYPES = list(CROP_YIELD_BENCHMARKS.keys())
SOIL_TYPES = ['clay', 'loam', 'sandy_loam', 'clay_loam']
IRRIG_TYPES = ['rainfed', 'drip', 'sprinkler', 'furrow']


def _encode_categorical(value, categories, default=0):
    """Safe label encoding — returns index or 0 if unknown."""
    try:
        return categories.index(str(value).lower()) if value else default
    except ValueError:
        return default


# ════════════════════════════════════════════════════════════════
# 1. YIELD PREDICTION MODEL
# ════════════════════════════════════════════════════════════════

class YieldPredictionModel:
    """
    Predicts expected yield (tons/ha) for a farm.

    Features:
      - ndvi_value, health_score, moisture_percent
      - area_ha, crop_type (encoded), soil_type (encoded)
      - irrigation (encoded), days_since_planting
    """

    MODEL_PATH = os.path.join(MODEL_DIR, 'yield_model.joblib')

    def __init__(self):
        self.model = None
        self.mae   = None

    def _build_features(self, row):
        days_planted = (date.today() - row['planting_date']).days if row.get('planting_date') else 60
        return [
            float(row.get('ndvi_value')      or 0.5),
            float(row.get('health_score')    or 50),
            float(row.get('moisture_percent')or 45),
            float(row.get('area_ha')         or 2.0),
            _encode_categorical(row.get('crop_type'),   CROP_TYPES),
            _encode_categorical(row.get('soil_type'),   SOIL_TYPES),
            _encode_categorical(row.get('irrigation'),  IRRIG_TYPES),
            min(days_planted, 365),
        ]

    def _generate_training_data(self, db_rows):
        """
        Augment sparse DB data with synthetic samples drawn from
        agronomic distributions so the model generalises.
        """
        X, y = [], []

        # Real DB rows
        for row in db_rows:
            bench = CROP_YIELD_BENCHMARKS.get(row.get('crop_type', 'maize'),
                                              CROP_YIELD_BENCHMARKS['maize'])
            ndvi    = float(row.get('ndvi_value')  or 0.5)
            health  = float(row.get('health_score') or 50) / 100
            # Ground-truth yield derived from actual estimate if present
            yield_val = float(row.get('yield_estimate_tons') or (
                    bench['min'] + (bench['max'] - bench['min']) * health * 0.8
            ))
            X.append(self._build_features(row))
            y.append(yield_val)

        # Synthetic augmentation — 600 samples
        rng = np.random.default_rng(42)
        for _ in range(600):
            crop   = rng.choice(CROP_TYPES)
            bench  = CROP_YIELD_BENCHMARKS[crop]
            ndvi   = float(rng.uniform(0.15, 0.90))
            health = float(rng.uniform(20, 98))
            moist  = float(rng.uniform(15, 85))
            area   = float(rng.uniform(0.5, 15))
            soil   = rng.choice(SOIL_TYPES)
            irrig  = rng.choice(IRRIG_TYPES)
            days   = int(rng.integers(20, 180))
            planting = date.today() - timedelta(days=int(days))

            # Agronomic yield model: ndvi and health are primary drivers
            ndvi_factor   = ndvi / bench['optimal_ndvi']
            health_factor = health / 100
            irrig_bonus   = 1.15 if irrig in ('drip', 'sprinkler') else 1.0
            soil_bonus    = 1.10 if soil == 'loam' else 0.95 if soil == 'sandy_loam' else 1.0
            base_yield    = bench['min'] + (bench['max'] - bench['min']) * ndvi_factor * health_factor
            yield_val     = float(np.clip(base_yield * irrig_bonus * soil_bonus
                                          * rng.uniform(0.88, 1.12), bench['min'] * 0.5, bench['max'] * 1.1))

            X.append([ndvi, health, moist, area,
                      _encode_categorical(crop, CROP_TYPES),
                      _encode_categorical(soil, SOIL_TYPES),
                      _encode_categorical(irrig, IRRIG_TYPES),
                      days])
            y.append(yield_val)

        return np.array(X), np.array(y)

    def train(self, db_rows):
        X, y = self._generate_training_data(db_rows)
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model = RandomForestRegressor(
            n_estimators=200, max_depth=10,
            min_samples_leaf=3, random_state=42, n_jobs=-1
        )
        self.model.fit(X_tr, y_tr)
        self.mae = round(mean_absolute_error(y_te, self.model.predict(X_te)), 3)
        joblib.dump({'model': self.model, 'mae': self.mae}, self.MODEL_PATH)
        return self.mae

    def load(self):
        if os.path.exists(self.MODEL_PATH):
            data = joblib.load(self.MODEL_PATH)
            self.model = data['model']
            self.mae   = data['mae']
            return True
        return False

    def predict(self, farm_data):
        if self.model is None:
            raise RuntimeError('Model not trained. Call train() first.')
        features = np.array([self._build_features(farm_data)])
        pred     = float(self.model.predict(features)[0])
        crop     = farm_data.get('crop_type', 'maize')
        bench    = CROP_YIELD_BENCHMARKS.get(crop, CROP_YIELD_BENCHMARKS['maize'])
        pct      = round((pred / bench['max']) * 100)
        return {
            'predicted_yield_tons_ha': round(pred, 2),
            'total_yield_tons':        round(pred * float(farm_data.get('area_ha') or 1), 2),
            'benchmark_min':           bench['min'],
            'benchmark_max':           bench['max'],
            'performance_pct':         min(pct, 100),
            'rating':                  'Excellent' if pct >= 80 else 'Good' if pct >= 60
            else 'Fair' if pct >= 40 else 'Poor',
            'model_mae':               self.mae,
        }


# ════════════════════════════════════════════════════════════════
# 2. PEST & DISEASE RISK MODEL
# ════════════════════════════════════════════════════════════════

RISK_LEVELS = ['low', 'medium', 'high', 'critical']

class PestRiskModel:
    """
    Classifies pest & disease risk level for a farm.

    Features:
      - moisture_percent, days_since_rain
      - temperature, humidity, rainfall_mm
      - health_score trend (last 3 readings delta)
      - crop_type (encoded), days_since_planting
    """

    MODEL_PATH = os.path.join(MODEL_DIR, 'pest_risk_model.joblib')

    def __init__(self):
        self.model = None
        self.accuracy = None

    def _build_features(self, row):
        return [
            float(row.get('moisture_percent') or 45),
            float(row.get('days_since_rain')  or 5),
            float(row.get('temperature')      or 25),
            float(row.get('humidity')         or 70),
            float(row.get('rainfall_mm')      or 5),
            float(row.get('health_score')     or 60),
            float(row.get('health_trend')     or 0),   # score delta over last 3 readings
            _encode_categorical(row.get('crop_type'), CROP_TYPES),
            float(row.get('days_since_planting') or 60),
        ]

    def _risk_label(self, moisture, days_rain, temp, humidity, health, trend):
        """Agronomic rules to derive ground-truth labels for training."""
        score = 0
        if moisture > 70:       score += 2   # waterlogged — fungal risk
        if moisture < 25:       score += 1   # drought stress
        if days_rain > 10:      score += 1   # dry spell
        if temp > 30:           score += 1   # heat stress
        if humidity > 80:       score += 2   # fungal / bacterial
        if health < 40:         score += 3   # already poor
        if trend < -10:         score += 2   # declining fast
        if score >= 7:  return 3  # critical
        if score >= 5:  return 2  # high
        if score >= 3:  return 1  # medium
        return 0                  # low

    def _generate_training_data(self, db_rows):
        X, y = [], []

        for row in db_rows:
            label = self._risk_label(
                float(row.get('moisture_percent') or 45),
                float(row.get('days_since_rain')  or 5),
                float(row.get('temperature')      or 25),
                float(row.get('humidity')         or 70),
                float(row.get('health_score')     or 60),
                float(row.get('health_trend')     or 0),
            )
            X.append(self._build_features(row))
            y.append(label)

        rng = np.random.default_rng(99)
        for _ in range(800):
            crop    = rng.choice(CROP_TYPES)
            moist   = float(rng.uniform(10, 90))
            d_rain  = int(rng.integers(0, 21))
            temp    = float(rng.uniform(15, 38))
            humid   = float(rng.uniform(40, 95))
            rain    = float(rng.uniform(0, 30))
            health  = float(rng.uniform(20, 98))
            trend   = float(rng.uniform(-20, 10))
            days    = int(rng.integers(10, 200))
            label   = self._risk_label(moist, d_rain, temp, humid, health, trend)
            X.append([moist, d_rain, temp, humid, rain, health, trend,
                      _encode_categorical(crop, CROP_TYPES), days])
            y.append(label)

        return np.array(X), np.array(y)

    def train(self, db_rows):
        X, y = self._generate_training_data(db_rows)
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model = RandomForestClassifier(
            n_estimators=200, max_depth=12,
            min_samples_leaf=2, random_state=42, n_jobs=-1
        )
        self.model.fit(X_tr, y_tr)
        self.accuracy = round(accuracy_score(y_te, self.model.predict(X_te)), 3)
        joblib.dump({'model': self.model, 'accuracy': self.accuracy}, self.MODEL_PATH)
        return self.accuracy

    def load(self):
        if os.path.exists(self.MODEL_PATH):
            data = joblib.load(self.MODEL_PATH)
            self.model    = data['model']
            self.accuracy = data['accuracy']
            return True
        return False

    def predict(self, farm_data):
        if self.model is None:
            raise RuntimeError('Model not trained.')
        features  = np.array([self._build_features(farm_data)])
        pred_idx  = int(self.model.predict(features)[0])
        proba     = self.model.predict_proba(features)[0]
        level     = RISK_LEVELS[pred_idx]
        confidence= round(float(proba[pred_idx]) * 100)

        # Build contributing factors
        factors = []
        m = float(farm_data.get('moisture_percent') or 45)
        h = float(farm_data.get('humidity')         or 70)
        t = float(farm_data.get('temperature')      or 25)
        d = float(farm_data.get('days_since_rain')  or 5)
        s = float(farm_data.get('health_score')     or 60)
        if m > 70:    factors.append('High soil moisture — fungal disease risk elevated')
        if m < 25:    factors.append('Low soil moisture — drought stress weakens crop immunity')
        if h > 80:    factors.append('High humidity — favourable conditions for fungal pathogens')
        if t > 30:    factors.append('High temperature — heat stress and insect activity increased')
        if d > 10:    factors.append('Extended dry period — pest pressure typically increases')
        if s < 40:    factors.append('Low health score — crop already under stress')
        if not factors:
            factors.append('No significant risk factors detected')

        return {
            'risk_level':      level,
            'risk_index':      pred_idx,
            'confidence_pct':  confidence,
            'probabilities':   {RISK_LEVELS[i]: round(float(p)*100) for i, p in enumerate(proba)},
            'contributing_factors': factors,
            'recommendation':  {
                'low':      'Continue standard monitoring. No immediate action required.',
                'medium':   'Increase scouting frequency. Consider preventive fungicide application.',
                'high':     'Apply targeted pesticide or fungicide within 48 hours. Improve drainage if waterlogged.',
                'critical': 'Immediate intervention required. Consult agronomist. Risk of significant crop loss.',
            }[level],
            'model_accuracy': self.accuracy,
        }


# ════════════════════════════════════════════════════════════════
# 3. CROP HEALTH FORECAST MODEL
# ════════════════════════════════════════════════════════════════

class HealthForecastModel:
    """
    Forecasts crop health score 14 days ahead.

    Features:
      - current health_score, ndvi, moisture_percent
      - temperature, humidity, rainfall_mm
      - health_trend (7-day delta), days_since_planting
      - crop_type, irrigation
    """

    MODEL_PATH = os.path.join(MODEL_DIR, 'health_forecast_model.joblib')

    def __init__(self):
        self.model = None
        self.mae   = None

    def _build_features(self, row):
        return [
            float(row.get('health_score')     or 60),
            float(row.get('ndvi_value')        or 0.5),
            float(row.get('moisture_percent')  or 45),
            float(row.get('temperature')       or 25),
            float(row.get('humidity')          or 70),
            float(row.get('rainfall_mm')       or 5),
            float(row.get('health_trend')      or 0),
            float(row.get('days_since_planting') or 60),
            _encode_categorical(row.get('crop_type'),  CROP_TYPES),
            _encode_categorical(row.get('irrigation'), IRRIG_TYPES),
        ]

    def _forecast_score(self, health, ndvi, moisture, temp, humidity, rainfall, trend):
        """Agronomic projection for synthetic targets."""
        base   = health + trend * 0.5
        ndvi_f = (ndvi - 0.5) * 15
        moist_f= 0 if 35 <= moisture <= 65 else (-8 if moisture < 20 else -5 if moisture < 35 else -3)
        temp_f = 0 if 20 <= temp <= 30 else (-5 if temp > 33 else -2)
        rain_f = min(rainfall * 0.3, 5)
        score  = base + ndvi_f + moist_f + temp_f + rain_f
        return float(np.clip(score, 5, 100))

    def _generate_training_data(self, db_rows):
        X, y = [], []

        for row in db_rows:
            target = self._forecast_score(
                float(row.get('health_score')    or 60),
                float(row.get('ndvi_value')       or 0.5),
                float(row.get('moisture_percent') or 45),
                float(row.get('temperature')      or 25),
                float(row.get('humidity')         or 70),
                float(row.get('rainfall_mm')      or 5),
                float(row.get('health_trend')     or 0),
            )
            X.append(self._build_features(row))
            y.append(target)

        rng = np.random.default_rng(7)
        for _ in range(700):
            crop   = rng.choice(CROP_TYPES)
            irrig  = rng.choice(IRRIG_TYPES)
            health = float(rng.uniform(20, 98))
            ndvi   = float(rng.uniform(0.15, 0.90))
            moist  = float(rng.uniform(10, 85))
            temp   = float(rng.uniform(15, 38))
            humid  = float(rng.uniform(40, 95))
            rain   = float(rng.uniform(0, 30))
            trend  = float(rng.uniform(-15, 10))
            days   = int(rng.integers(10, 200))
            target = self._forecast_score(health, ndvi, moist, temp, humid, rain, trend)
            X.append([health, ndvi, moist, temp, humid, rain, trend, days,
                      _encode_categorical(crop, CROP_TYPES),
                      _encode_categorical(irrig, IRRIG_TYPES)])
            y.append(target)

        return np.array(X), np.array(y)

    def train(self, db_rows):
        X, y = self._generate_training_data(db_rows)
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model = GradientBoostingRegressor(
            n_estimators=200, max_depth=5, learning_rate=0.08,
            subsample=0.8, random_state=42
        )
        self.model.fit(X_tr, y_tr)
        self.mae = round(mean_absolute_error(y_te, self.model.predict(X_te)), 3)
        joblib.dump({'model': self.model, 'mae': self.mae}, self.MODEL_PATH)
        return self.mae

    def load(self):
        if os.path.exists(self.MODEL_PATH):
            data = joblib.load(self.MODEL_PATH)
            self.model = data['model']
            self.mae   = data['mae']
            return True
        return False

    def predict(self, farm_data):
        if self.model is None:
            raise RuntimeError('Model not trained.')
        features       = np.array([self._build_features(farm_data)])
        current_score  = float(farm_data.get('health_score') or 60)
        forecast_score = float(np.clip(self.model.predict(features)[0], 5, 100))
        delta          = round(forecast_score - current_score, 1)
        trend_label    = 'Improving' if delta > 3 else 'Declining' if delta < -3 else 'Stable'

        return {
            'current_score':      round(current_score, 1),
            'forecast_score_14d': round(forecast_score, 1),
            'delta':              delta,
            'trend':              trend_label,
            'forecast_status':    (
                'Excellent' if forecast_score >= 80 else
                'Good'      if forecast_score >= 60 else
                'Fair'      if forecast_score >= 40 else 'Poor'
            ),
            'confidence_note': f'±{self.mae} pts (model MAE)',
            'model_mae':       self.mae,
        }


# ════════════════════════════════════════════════════════════════
# 4. LAND COVER CLASSIFICATION MODEL
# ════════════════════════════════════════════════════════════════

LAND_COVER_CLASSES = [
    'cropland_healthy', 'cropland_stressed', 'cropland_fallow',
    'forest_dense', 'forest_degraded',
    'grassland', 'wetland', 'bare_soil', 'urban_buildup', 'water_body'
]

class LandCoverModel:
    """
    Classifies land cover type from spectral indices.

    Features:
      - ndvi, savi, ndwi, lai
      - health_score, moisture_percent
      - latitude, longitude (spatial context)
    """

    MODEL_PATH = os.path.join(MODEL_DIR, 'land_cover_model.joblib')

    def __init__(self):
        self.model    = None
        self.accuracy = None

    def _build_features(self, row):
        return [
            float(row.get('ndvi')             or 0.0),
            float(row.get('savi')             or 0.0),
            float(row.get('ndwi')             or 0.0),
            float(row.get('lai')              or 0.0),
            float(row.get('health_score')     or 50),
            float(row.get('moisture_percent') or 45),
            float(row.get('latitude')         or 0.28),
            float(row.get('longitude')        or 34.75),
        ]

    def _class_from_indices(self, ndvi, savi, ndwi, moisture, health):
        """Spectral rules to label synthetic samples."""
        if ndwi > 0.3 and moisture > 70:  return 9  # water_body
        if ndvi < 0.05:                    return 7  # bare_soil
        if ndvi < 0.15:                    return 8  # urban_buildup
        if ndvi > 0.75 and savi > 0.5:    return 3  # forest_dense
        if ndvi > 0.55 and savi > 0.35:   return 4  # forest_degraded
        if ndwi > 0.2:                     return 5  # wetland
        if ndvi > 0.45 and health >= 60:   return 0  # cropland_healthy
        if ndvi > 0.25 and health >= 35:   return 1  # cropland_stressed
        if 0.10 < ndvi <= 0.25:            return 2  # cropland_fallow
        return 5                                      # grassland

    def _generate_training_data(self):
        X, y = [], []
        rng = np.random.default_rng(55)

        for cls_idx, _ in enumerate(LAND_COVER_CLASSES):
            for _ in range(120):  # 120 samples per class
                if cls_idx == 9:   # water
                    ndvi, savi, ndwi = rng.uniform(-0.1, 0.05), rng.uniform(-0.05, 0.05), rng.uniform(0.3, 0.8)
                    moist, health = rng.uniform(75, 100), rng.uniform(20, 40)
                elif cls_idx == 7:  # bare soil
                    ndvi, savi, ndwi = rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05), rng.uniform(-0.3, 0.0)
                    moist, health = rng.uniform(5, 25), rng.uniform(10, 30)
                elif cls_idx == 8:  # urban
                    ndvi, savi, ndwi = rng.uniform(0.05, 0.18), rng.uniform(0.03, 0.15), rng.uniform(-0.2, 0.05)
                    moist, health = rng.uniform(10, 35), rng.uniform(15, 35)
                elif cls_idx == 3:  # dense forest
                    ndvi, savi, ndwi = rng.uniform(0.75, 0.95), rng.uniform(0.5, 0.75), rng.uniform(0.1, 0.4)
                    moist, health = rng.uniform(50, 85), rng.uniform(70, 95)
                elif cls_idx == 4:  # degraded forest
                    ndvi, savi, ndwi = rng.uniform(0.50, 0.75), rng.uniform(0.30, 0.55), rng.uniform(0.05, 0.25)
                    moist, health = rng.uniform(40, 70), rng.uniform(50, 75)
                elif cls_idx == 5:  # wetland
                    ndvi, savi, ndwi = rng.uniform(0.25, 0.55), rng.uniform(0.20, 0.45), rng.uniform(0.15, 0.45)
                    moist, health = rng.uniform(65, 95), rng.uniform(45, 75)
                elif cls_idx == 6:  # grassland
                    ndvi, savi, ndwi = rng.uniform(0.15, 0.40), rng.uniform(0.10, 0.35), rng.uniform(-0.1, 0.15)
                    moist, health = rng.uniform(25, 55), rng.uniform(35, 65)
                elif cls_idx == 0:  # cropland healthy
                    ndvi, savi, ndwi = rng.uniform(0.45, 0.85), rng.uniform(0.35, 0.65), rng.uniform(0.05, 0.35)
                    moist, health = rng.uniform(35, 70), rng.uniform(60, 98)
                elif cls_idx == 1:  # cropland stressed
                    ndvi, savi, ndwi = rng.uniform(0.25, 0.50), rng.uniform(0.15, 0.40), rng.uniform(-0.1, 0.15)
                    moist, health = rng.uniform(15, 45), rng.uniform(25, 55)
                else:               # cropland fallow
                    ndvi, savi, ndwi = rng.uniform(0.10, 0.28), rng.uniform(0.05, 0.22), rng.uniform(-0.15, 0.10)
                    moist, health = rng.uniform(10, 40), rng.uniform(15, 40)

                lai = max(0, float(3.618 * ndvi**2 + 0.118))
                lat = float(rng.uniform(0.05, 0.55))
                lon = float(rng.uniform(34.35, 35.00))
                X.append([ndvi, savi, ndwi, lai, health, moist, lat, lon])
                y.append(cls_idx)

        return np.array(X), np.array(y)

    def train(self, db_rows=None):
        X, y = self._generate_training_data()
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2,
                                                  random_state=42, stratify=y)
        self.model = RandomForestClassifier(
            n_estimators=300, max_depth=15,
            min_samples_leaf=2, random_state=42, n_jobs=-1
        )
        self.model.fit(X_tr, y_tr)
        self.accuracy = round(accuracy_score(y_te, self.model.predict(X_te)), 3)
        joblib.dump({'model': self.model, 'accuracy': self.accuracy,
                     'classes': LAND_COVER_CLASSES}, self.MODEL_PATH)
        return self.accuracy

    def load(self):
        if os.path.exists(self.MODEL_PATH):
            data = joblib.load(self.MODEL_PATH)
            self.model    = data['model']
            self.accuracy = data['accuracy']
            return True
        return False

    def predict(self, spectral_data):
        if self.model is None:
            raise RuntimeError('Model not trained.')
        features  = np.array([self._build_features(spectral_data)])
        pred_idx  = int(self.model.predict(features)[0])
        proba     = self.model.predict_proba(features)[0]
        label     = LAND_COVER_CLASSES[pred_idx]
        confidence= round(float(proba[pred_idx]) * 100)

        top3 = sorted(
            [{'class': LAND_COVER_CLASSES[i], 'probability_pct': round(float(p)*100)}
             for i, p in enumerate(proba)],
            key=lambda x: x['probability_pct'], reverse=True
        )[:3]

        return {
            'land_cover_class':  label,
            'label':             label.replace('_', ' ').title(),
            'confidence_pct':    confidence,
            'top_3_classes':     top3,
            'model_accuracy':    self.accuracy,
        }