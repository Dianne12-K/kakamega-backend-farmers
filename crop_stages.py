from datetime import datetime

class CropStageAnalyzer:
    """Determine crop growth stage based on days since planting and NDVI"""

    CROP_STAGES = {
        'maize': [
            {'name': 'Germination', 'days': (0, 10), 'ndvi_range': (0.1, 0.3)},
            {'name': 'Seedling', 'days': (10, 25), 'ndvi_range': (0.2, 0.4)},
            {'name': 'Vegetative', 'days': (25, 50), 'ndvi_range': (0.4, 0.7)},
            {'name': 'Tasseling/Flowering', 'days': (50, 70), 'ndvi_range': (0.6, 0.8)},
            {'name': 'Grain Filling', 'days': (70, 100), 'ndvi_range': (0.6, 0.8)},
            {'name': 'Maturity', 'days': (100, 120), 'ndvi_range': (0.4, 0.7)},
            {'name': 'Harvest Ready', 'days': (120, 140), 'ndvi_range': (0.3, 0.5)}
        ],
        'sugarcane': [
            {'name': 'Germination', 'days': (0, 30), 'ndvi_range': (0.2, 0.4)},
            {'name': 'Tillering', 'days': (30, 120), 'ndvi_range': (0.4, 0.7)},
            {'name': 'Grand Growth', 'days': (120, 270), 'ndvi_range': (0.7, 0.9)},
            {'name': 'Maturity', 'days': (270, 365), 'ndvi_range': (0.65, 0.85)},
            {'name': 'Harvest Ready', 'days': (365, 450), 'ndvi_range': (0.6, 0.8)}
        ]
    }

    def get_growth_stage(self, crop_type, planting_date, current_ndvi=None):
        """
        Determine current growth stage

        Args:
            crop_type: Type of crop
            planting_date: Date crop was planted (string or datetime)
            current_ndvi: Optional NDVI value for validation

        Returns:
            dict with stage info
        """
        if isinstance(planting_date, str):
            planting_date = datetime.strptime(planting_date, '%Y-%m-%d')

        days_since_planting = (datetime.now() - planting_date).days

        crop_type = crop_type.lower()
        stages = self.CROP_STAGES.get(crop_type)

        if not stages:
            return {
                'stage_name': 'Unknown',
                'days_since_planting': days_since_planting,
                'stage_progress': 0,
                'description': f'Growth stage data not available for {crop_type}'
            }

        # Find matching stage
        for stage in stages:
            min_days, max_days = stage['days']
            if min_days <= days_since_planting <= max_days:
                # Calculate progress within stage
                stage_duration = max_days - min_days
                stage_progress = int(((days_since_planting - min_days) / stage_duration) * 100)

                # Check if NDVI matches expected range
                ndvi_status = 'normal'
                if current_ndvi:
                    min_ndvi, max_ndvi = stage['ndvi_range']
                    if current_ndvi < min_ndvi:
                        ndvi_status = 'below_expected'
                    elif current_ndvi > max_ndvi:
                        ndvi_status = 'above_expected'

                return {
                    'stage_name': stage['name'],
                    'days_since_planting': days_since_planting,
                    'stage_progress': stage_progress,
                    'expected_ndvi_range': stage['ndvi_range'],
                    'ndvi_status': ndvi_status,
                    'days_in_stage': days_since_planting - min_days,
                    'days_to_next_stage': max_days - days_since_planting,
                    'description': self._get_stage_description(crop_type, stage['name'])
                }

        # Past last stage
        return {
            'stage_name': 'Overdue Harvest',
            'days_since_planting': days_since_planting,
            'stage_progress': 100,
            'description': f'Crop should have been harvested by now ({days_since_planting} days)'
        }

    def _get_stage_description(self, crop_type, stage_name):
        """Get description and recommendations for stage"""
        descriptions = {
            'maize': {
                'Germination': 'Seeds sprouting. Ensure adequate moisture.',
                'Seedling': 'Young plants establishing. Control weeds.',
                'Vegetative': 'Rapid growth. Apply nitrogen fertilizer.',
                'Tasseling/Flowering': 'Critical water period. Ensure no stress.',
                'Grain Filling': 'Grains developing. Maintain moisture.',
                'Maturity': 'Drying down. Prepare for harvest.',
                'Harvest Ready': 'Ready to harvest. Check moisture content.'
            },
            'sugarcane': {
                'Germination': 'Shoots emerging. Keep soil moist.',
                'Tillering': 'Multiple shoots forming. Apply fertilizer.',
                'Grand Growth': 'Rapid cane development. Peak water needs.',
                'Maturity': 'Sugar accumulation. Reduce water.',
                'Harvest Ready': 'Maximum sugar content. Harvest window open.'
            }
        }

        return descriptions.get(crop_type, {}).get(stage_name, 'Monitor crop development')

    def get_stage_recommendations(self, crop_type, stage_name, health_score, moisture_status):
        """Get specific recommendations based on growth stage and conditions"""

        recommendations = []

        # Stage-specific recommendations
        if crop_type.lower() == 'maize':
            if stage_name == 'Vegetative':
                recommendations.append({
                    'action': 'Apply top-dressing fertilizer',
                    'timing': 'Within next 5 days',
                    'details': 'Apply 50kg CAN per acre'
                })
            elif stage_name == 'Tasseling/Flowering':
                recommendations.append({
                    'action': 'Ensure consistent moisture',
                    'timing': 'Daily monitoring',
                    'details': 'Water stress now severely reduces yield'
                })
            elif stage_name == 'Harvest Ready':
                recommendations.append({
                    'action': 'Harvest within 2 weeks',
                    'timing': 'When grain moisture is 20-25%',
                    'details': 'Delayed harvest risks pest damage and grain loss'
                })

        # Health-based recommendations
        if health_score < 50:
            recommendations.append({
                'action': 'Urgent crop inspection needed',
                'timing': 'Within 24 hours',
                'details': f'Poor health at {stage_name} stage is critical'
            })

        # Moisture-based recommendations
        if moisture_status in ['dry', 'low'] and stage_name in ['Tasseling/Flowering', 'Grand Growth']:
            recommendations.append({
                'action': 'URGENT: Irrigate immediately',
                'timing': 'Today',
                'details': f'Critical growth stage - water stress will permanently reduce yield'
            })

        return recommendations