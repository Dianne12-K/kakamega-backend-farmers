"""
train_models.py
---------------
Run this script ONCE after seeding the database to pre-train and
save all four ML models to disk.

Usage:
    python train_models.py

After running, the saved model files in ml/saved_models/ will be
loaded automatically every time Flask starts — no retraining needed
unless you run this script again or call POST /api/ml/retrain.
"""

import os, sys, time
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from ml.service import ml_service

def main():
    print('\n=== GeoAI Platform — ML Model Training ===\n')
    app = create_app('development')

    with app.app_context():
        rows = ml_service._fetch_training_rows()
        print(f'Training rows fetched from DB: {len(rows)}\n')

        models = [
            ('Yield Prediction       (RandomForestRegressor)',     ml_service.yield_model,    'mae'),
            ('Pest & Disease Risk    (RandomForestClassifier)',     ml_service.pest_model,     'accuracy'),
            ('Crop Health Forecast   (GradientBoostingRegressor)',  ml_service.forecast_model, 'mae'),
            ('Land Cover Classification (RandomForestClassifier)',  ml_service.land_model,     'accuracy'),
        ]

        for label, model, metric_key in models:
            print(f'  Training: {label}')
            t0 = time.time()
            if metric_key == 'mae':
                val = model.train(rows)
                print(f'    MAE      = {val} points')
            else:
                val = model.train(rows if label != 'Land Cover Classification (RandomForestClassifier)' else None)
                print(f'    Accuracy = {val * 100:.1f}%')
            print(f'    Time     = {time.time() - t0:.1f}s\n')

    print('All models saved to ml/saved_models/')
    print('Flask will load them automatically on next startup.\n')

if __name__ == '__main__':
    main()