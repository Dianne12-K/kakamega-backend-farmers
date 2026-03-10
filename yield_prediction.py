import numpy as np
from datetime import datetime

class YieldPredictor:
    """Predict crop yield based on NDVI trends, weather, and historical data"""

    # Historical yield baselines (tons per hectare)
    BASELINE_YIELDS = {
        'maize': {
            'poor': 1.5,
            'average': 2.5,
            'good': 3.5,
            'excellent': 4.5
        },
        'sugarcane': {
            'poor': 40,
            'average': 65,
            'good': 85,
            'excellent': 105
        },
        'beans': {
            'poor': 0.4,
            'average': 0.8,
            'good': 1.2,
            'excellent': 1.6
        }
    }

    def predict_yield(self, crop_type, area_ha, ndvi_history, current_health_score,
                      moisture_status, growth_stage, weather_forecast):
        """
        Predict final yield based on multiple factors

        Returns:
            dict with yield prediction and confidence
        """
        crop_type = crop_type.lower()
        baseline = self.BASELINE_YIELDS.get(crop_type, self.BASELINE_YIELDS['maize'])

        # Start with average baseline
        predicted_yield_per_ha = baseline['average']

        # Factor 1: NDVI trend (40% weight)
        ndvi_factor = self._calculate_ndvi_factor(ndvi_history)
        predicted_yield_per_ha *= ndvi_factor

        # Factor 2: Current health (30% weight)
        health_factor = self._calculate_health_factor(current_health_score)
        predicted_yield_per_ha *= (0.7 + (health_factor * 0.3))

        # Factor 3: Water availability (20% weight)
        moisture_factor = self._calculate_moisture_factor(moisture_status)
        predicted_yield_per_ha *= moisture_factor

        # Factor 4: Weather forecast impact (10% weight)
        weather_factor = self._calculate_weather_factor(weather_forecast, growth_stage)
        predicted_yield_per_ha *= weather_factor

        # Total yield
        total_yield = predicted_yield_per_ha * area_ha

        # Calculate confidence based on data quality
        confidence = self._calculate_confidence(ndvi_history, growth_stage)

        # Yield range (±15%)
        yield_range = {
            'min': total_yield * 0.85,
            'max': total_yield * 1.15,
            'most_likely': total_yield
        }

        # Performance category
        if predicted_yield_per_ha >= baseline['excellent']:
            performance = 'excellent'
        elif predicted_yield_per_ha >= baseline['good']:
            performance = 'good'
        elif predicted_yield_per_ha >= baseline['average']:
            performance = 'average'
        else:
            performance = 'poor'

        # Revenue estimation (Kakamega prices - update seasonally)
        price_per_unit = self._get_market_price(crop_type)
        estimated_revenue = total_yield * price_per_unit

        return {
            'predicted_yield_total': round(total_yield, 2),
            'predicted_yield_per_ha': round(predicted_yield_per_ha, 2),
            'yield_range': {k: round(v, 2) for k, v in yield_range.items()},
            'performance_category': performance,
            'confidence_level': confidence,
            'confidence_percentage': int(confidence * 100),
            'estimated_revenue': round(estimated_revenue, 0),
            'price_per_unit': price_per_unit,
            'unit': self._get_unit(crop_type),
            'factors': {
                'ndvi_contribution': round(ndvi_factor, 2),
                'health_contribution': round(health_factor, 2),
                'moisture_contribution': round(moisture_factor, 2),
                'weather_contribution': round(weather_factor, 2)
            },
            'harvest_estimate': self._estimate_harvest_date(growth_stage),
            'recommendations': self._get_yield_optimization_tips(performance, crop_type)
        }

    def _calculate_ndvi_factor(self, ndvi_history):
        """Calculate yield factor from NDVI trend"""
        if not ndvi_history or len(ndvi_history) < 3:
            return 1.0

        # Recent NDVI values (last 30 days)
        recent_ndvi = [h['ndvi_value'] for h in ndvi_history[-6:]]
        avg_ndvi = np.mean(recent_ndvi)

        # NDVI to yield factor (empirical relationship)
        if avg_ndvi >= 0.75:
            return 1.3  # Excellent
        elif avg_ndvi >= 0.65:
            return 1.15  # Good
        elif avg_ndvi >= 0.50:
            return 1.0  # Average
        elif avg_ndvi >= 0.35:
            return 0.80  # Below average
        else:
            return 0.60  # Poor

    def _calculate_health_factor(self, health_score):
        """Convert health score to yield factor"""
        return health_score / 100

    def _calculate_moisture_factor(self, moisture_status):
        """Impact of soil moisture on yield"""
        factors = {
            'wet': 0.95,      # Too much water
            'adequate': 1.0,   # Ideal
            'low': 0.85,       # Starting to stress
            'dry': 0.65        # Severe stress
        }
        return factors.get(moisture_status, 1.0)

    def _calculate_weather_factor(self, weather_forecast, growth_stage):
        """Predict weather impact on final yield"""
        if not weather_forecast:
            return 1.0

        # Check for adverse weather in critical growth stages
        critical_stages = ['Tasseling/Flowering', 'Grain Filling', 'Grand Growth']

        if growth_stage in critical_stages:
            # Check for drought or excessive rain
            total_rain = sum([day['rain_mm'] for day in weather_forecast])

            if total_rain < 5:  # Drought
                return 0.90
            elif total_rain > 150:  # Too much rain
                return 0.92

        return 1.0

    def _calculate_confidence(self, ndvi_history, growth_stage):
        """Calculate prediction confidence"""
        confidence = 0.5  # Base confidence

        # More data = higher confidence
        if len(ndvi_history) > 10:
            confidence += 0.2
        elif len(ndvi_history) > 5:
            confidence += 0.1

        # Later stage = higher confidence
        advanced_stages = ['Grain Filling', 'Maturity', 'Harvest Ready']
        if growth_stage in advanced_stages:
            confidence += 0.3

        return min(1.0, confidence)

    def _get_market_price(self, crop_type):
        """Get current market price (update these regularly!)"""
        prices = {
            'maize': 4000,      # Ksh per 90kg bag → Ksh 44/kg
            'sugarcane': 4500,  # Ksh per ton
            'beans': 10000,     # Ksh per 90kg bag
            'tea': 35,          # Ksh per kg green leaf
            'coffee': 60        # Ksh per kg cherry
        }
        return prices.get(crop_type, 0)

    def _get_unit(self, crop_type):
        """Get unit for crop"""
        units = {
            'maize': 'bags (90kg)',
            'sugarcane': 'tons',
            'beans': 'bags (90kg)',
            'tea': 'kg',
            'coffee': 'kg'
        }
        return units.get(crop_type, 'tons')

    def _estimate_harvest_date(self, growth_stage):
        """Estimate when crop will be ready to harvest"""
        # This would be calculated from planting date + growth stage
        # Simplified version here
        return "Estimated in 4-6 weeks"

    def _get_yield_optimization_tips(self, performance, crop_type):
        """Get tips to improve yield"""
        if performance in ['excellent', 'good']:
            return [
                "Maintain current management practices",
                "Monitor closely to sustain high performance",
                "Plan for timely harvest"
            ]
        elif performance == 'average':
            return [
                "Consider foliar fertilizer application",
                "Ensure consistent moisture management",
                "Scout for pests and diseases"
            ]
        else:  # poor
            return [
                "Identify and address primary stress factors immediately",
                "Consider salvage strategies if too late in season",
                "Document issues for improved planning next season"
            ]