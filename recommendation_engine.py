from datetime import datetime, timedelta

class RecommendationEngine:
    def generate_recommendation(self, health_data, moisture_data, weather_data, farm_info):
        """
        Generate smart farming recommendation based on all variables

        Args:
            health_data: Dictionary with NDVI and health score
            moisture_data: Dictionary with soil moisture info
            weather_data: Dictionary with forecast
            farm_info: Dictionary with farm details

        Returns:
            Dictionary with priority, action, and reason
        """

        health_score = health_data.get('health_score', 0)
        moisture_percent = moisture_data.get('moisture_percent', 0)
        moisture_status = moisture_data.get('status', 'unknown')

        # Find next rain
        next_rain = self._find_next_rain(weather_data.get('forecast', []))

        # DECISION LOGIC

        # Critical: Very poor health + dry soil + no rain
        if health_score < 40 and moisture_status in ['dry', 'low'] and (next_rain is None or next_rain['days'] > 5):
            return {
                'priority': 'critical',
                'priority_label': '🔴 CRITICAL',
                'action': 'Immediate irrigation and inspection required',
                'reason': f'Crop health is very poor (score: {health_score}/100), soil moisture is {moisture_status}, and no significant rain expected for {next_rain["days"] if next_rain else "7+"} days. Immediate action needed to prevent crop failure.',
                'tasks': [
                    'Irrigate immediately (within 24 hours)',
                    'Inspect for pests and diseases',
                    'Consider applying emergency fertilizer'
                ]
            }

        # High Priority: Low moisture + no rain soon
        if moisture_status in ['dry', 'low'] and (next_rain is None or next_rain['days'] > 3):
            return {
                'priority': 'high',
                'priority_label': '🟠 HIGH PRIORITY',
                'action': 'Irrigate within 2-3 days',
                'reason': f'Soil moisture is {moisture_status} ({moisture_percent}%) and no rain expected for {next_rain["days"] if next_rain else "7+"} days. Crops will experience water stress soon.',
                'tasks': [
                    f'Plan irrigation for next 2-3 days',
                    'Monitor crop stress daily',
                    'Check irrigation equipment'
                ]
            }

        # Medium: Low moisture BUT rain coming
        if moisture_status in ['dry', 'low'] and next_rain and next_rain['days'] <= 3:
            return {
                'priority': 'medium',
                'priority_label': '🟡 MEDIUM PRIORITY',
                'action': f'Wait for rain expected in {next_rain["days"]} day(s)',
                'reason': f'Soil moisture is {moisture_status} ({moisture_percent}%), but rain is forecasted in {next_rain["days"]} day(s) with {next_rain["probability"]}% probability ({next_rain["amount"]}mm expected). Save irrigation costs.',
                'tasks': [
                    f'Monitor weather closely',
                    f'If no rain by {next_rain["date"]}, irrigate immediately',
                    'Prepare irrigation as backup plan'
                ]
            }

        # Poor health but adequate moisture
        if health_score < 50 and moisture_status in ['adequate', 'wet']:
            return {
                'priority': 'high',
                'priority_label': '🟠 HIGH PRIORITY',
                'action': 'Investigate crop health issues',
                'reason': f'Crop health is poor (score: {health_score}/100) despite adequate soil moisture ({moisture_percent}%). This suggests pest, disease, or nutrient deficiency problems.',
                'tasks': [
                    'Inspect crops for pests and diseases',
                    'Consider soil testing for nutrients',
                    'Consult agricultural extension officer',
                    'Check for proper drainage (avoid waterlogging)'
                ]
            }

        # Declining health
        if health_data.get('trend') == 'declining' and health_score < 70:
            return {
                'priority': 'medium',
                'priority_label': '🟡 MEDIUM PRIORITY',
                'action': 'Monitor crop health closely',
                'reason': f'Crop health is declining (current score: {health_score}/100). Early intervention can prevent serious issues.',
                'tasks': [
                    'Increase monitoring frequency',
                    'Check for early signs of stress',
                    'Ensure adequate water and nutrients',
                    'Scout for pests weekly'
                ]
            }

        # Too wet (overwatering risk)
        if moisture_status == 'wet' and next_rain and next_rain['days'] <= 2:
            return {
                'priority': 'medium',
                'priority_label': '🟡 MEDIUM PRIORITY',
                'action': 'Avoid irrigation - waterlogging risk',
                'reason': f'Soil moisture is already high ({moisture_percent}%) and more rain is expected in {next_rain["days"]} day(s). Excess water can damage roots.',
                'tasks': [
                    'Do NOT irrigate',
                    'Check drainage systems',
                    'Monitor for signs of waterlogging',
                    'Wait for soil to dry before next watering'
                ]
            }

        # Growth stage recommendations
        crop_type = farm_info.get('crop_type', '').lower()
        planting_date = farm_info.get('planting_date')

        if planting_date:
            growth_stage = self._calculate_growth_stage(planting_date, crop_type)
            stage_recommendation = self._get_stage_recommendation(
                growth_stage, crop_type, moisture_status, health_score
            )
            if stage_recommendation:
                return stage_recommendation

        # Default: Everything is okay
        return {
            'priority': 'low',
            'priority_label': '🟢 ALL GOOD',
            'action': 'Continue regular monitoring',
            'reason': f'Crop health is good (score: {health_score}/100), soil moisture is {moisture_status} ({moisture_percent}%). Continue with regular farm management practices.',
            'tasks': [
                'Monitor crops weekly',
                'Maintain regular irrigation schedule',
                'Scout for pests every 7-10 days',
                'Keep records of crop progress'
            ]
        }

    def _find_next_rain(self, forecast):
        """
        Find the next significant rain event in forecast
        Returns dict with days, amount, probability, date or None
        """
        if not forecast:
            return None

        today = datetime.now().date()

        for day_forecast in forecast:
            # Expecting forecast to have: date, rain_mm, rain_probability
            forecast_date = day_forecast.get('date')
            rain_mm = day_forecast.get('rain_mm', 0)
            rain_prob = day_forecast.get('rain_probability', 0)

            # Convert string date to date object if needed
            if isinstance(forecast_date, str):
                try:
                    forecast_date = datetime.strptime(forecast_date, '%Y-%m-%d').date()
                except ValueError:
                    continue

            # Consider significant rain: >5mm with >50% probability
            if rain_mm > 5 and rain_prob > 50:
                days_away = (forecast_date - today).days
                return {
                    'days': days_away,
                    'amount': round(rain_mm, 1),
                    'probability': rain_prob,
                    'date': forecast_date.strftime('%Y-%m-%d')
                }

        return None

    def _calculate_growth_stage(self, planting_date, crop_type):
        """
        Calculate current growth stage based on planting date
        Returns: 'seedling', 'vegetative', 'flowering', 'maturity'
        """
        if isinstance(planting_date, str):
            try:
                planting_date = datetime.strptime(planting_date, '%Y-%m-%d').date()
            except ValueError:
                return 'unknown'

        days_since_planting = (datetime.now().date() - planting_date).days

        # Growth stage thresholds by crop type (in days)
        stages = {
            'maize': [(0, 20, 'seedling'), (21, 60, 'vegetative'), (61, 90, 'flowering'), (91, 150, 'maturity')],
            'corn': [(0, 20, 'seedling'), (21, 60, 'vegetative'), (61, 90, 'flowering'), (91, 150, 'maturity')],
            'wheat': [(0, 15, 'seedling'), (16, 50, 'vegetative'), (51, 80, 'flowering'), (81, 130, 'maturity')],
            'rice': [(0, 25, 'seedling'), (26, 65, 'vegetative'), (66, 95, 'flowering'), (96, 150, 'maturity')],
            'soybean': [(0, 20, 'seedling'), (21, 50, 'vegetative'), (51, 85, 'flowering'), (86, 130, 'maturity')],
            'tomato': [(0, 30, 'seedling'), (31, 60, 'vegetative'), (61, 100, 'flowering'), (101, 150, 'maturity')],
            'potato': [(0, 30, 'seedling'), (31, 70, 'vegetative'), (71, 100, 'tuber_formation'), (101, 140, 'maturity')],
            'default': [(0, 20, 'seedling'), (21, 60, 'vegetative'), (61, 90, 'flowering'), (91, 140, 'maturity')]
        }

        crop_stages = stages.get(crop_type, stages['default'])

        for min_days, max_days, stage_name in crop_stages:
            if min_days <= days_since_planting <= max_days:
                return stage_name

        return 'maturity'  # Past final stage

    def _get_stage_recommendation(self, growth_stage, crop_type, moisture_status, health_score):
        """
        Generate recommendations based on crop growth stage
        """
        # Seedling stage - critical water needs
        if growth_stage == 'seedling':
            if moisture_status in ['dry', 'low']:
                return {
                    'priority': 'high',
                    'priority_label': '🟠 HIGH PRIORITY',
                    'action': 'Seedling stage requires consistent moisture',
                    'reason': f'Crops are in seedling stage - the most vulnerable period. Soil moisture is {moisture_status}. Seedlings need consistent water to establish roots.',
                    'tasks': [
                        'Irrigate gently to avoid washing seeds',
                        'Keep soil consistently moist (not waterlogged)',
                        'Water daily or every other day',
                        'Protect young plants from harsh sun if possible'
                    ]
                }

        # Flowering stage - critical for yield
        elif growth_stage == 'flowering':
            if health_score < 60:
                return {
                    'priority': 'high',
                    'priority_label': '🟠 HIGH PRIORITY',
                    'action': 'Flowering stage - critical for crop yield',
                    'reason': f'Crops are flowering (health score: {health_score}/100). This stage determines final yield. Stress now will significantly reduce harvest.',
                    'tasks': [
                        'Ensure adequate water - flowering needs 20-30% more water',
                        'Check for flower-damaging pests',
                        'Apply bloom fertilizer if needed',
                        'Avoid any stress factors during this period'
                    ]
                }

            if moisture_status in ['dry', 'low']:
                return {
                    'priority': 'high',
                    'priority_label': '🟠 HIGH PRIORITY',
                    'action': 'Critical irrigation needed during flowering',
                    'reason': f'Crops are flowering and soil is {moisture_status}. Water stress during flowering dramatically reduces yield.',
                    'tasks': [
                        'Irrigate immediately',
                        'Increase watering frequency',
                        'Consider drip irrigation for consistent moisture',
                        'Monitor daily - do not let soil dry out'
                    ]
                }

        # Maturity stage - reduce water
        elif growth_stage == 'maturity':
            if moisture_status == 'wet':
                return {
                    'priority': 'medium',
                    'priority_label': '🟡 MEDIUM PRIORITY',
                    'action': 'Reduce irrigation - approaching harvest',
                    'reason': f'Crops are maturing. Excess moisture now can cause quality issues and delay harvest.',
                    'tasks': [
                        'Reduce or stop irrigation',
                        'Allow soil to dry for better harvest conditions',
                        'Prepare for harvest in 1-3 weeks',
                        'Monitor for pre-harvest diseases'
                    ]
                }

        return None  # No stage-specific recommendation

    def get_irrigation_schedule(self, farm_info, moisture_data, weather_data):
        """
        Generate a 7-day irrigation schedule
        """
        schedule = []
        moisture_percent = moisture_data.get('moisture_percent', 50)
        crop_water_need = self._get_crop_water_requirement(farm_info.get('crop_type', 'default'))

        forecast = weather_data.get('forecast', [])

        for i in range(7):
            date = (datetime.now() + timedelta(days=i)).date()

            # Check if rain expected
            rain_expected = False
            rain_amount = 0
            for day_forecast in forecast:
                forecast_date = day_forecast.get('date')
                if isinstance(forecast_date, str):
                    forecast_date = datetime.strptime(forecast_date, '%Y-%m-%d').date()

                if forecast_date == date:
                    rain_mm = day_forecast.get('rain_mm', 0)
                    rain_prob = day_forecast.get('rain_probability', 0)
                    if rain_mm > 5 and rain_prob > 50:
                        rain_expected = True
                        rain_amount = rain_mm
                    break

            # Decision logic
            if rain_expected:
                recommendation = 'No irrigation needed - rain expected'
                water_amount = 0
            elif moisture_percent > 70:
                recommendation = 'No irrigation - soil moisture adequate'
                water_amount = 0
            elif moisture_percent < 30:
                recommendation = 'Irrigate heavily'
                water_amount = crop_water_need * 1.5
                moisture_percent += 30
            elif moisture_percent < 50:
                recommendation = 'Normal irrigation'
                water_amount = crop_water_need
                moisture_percent += 20
            else:
                recommendation = 'Light irrigation or skip'
                water_amount = crop_water_need * 0.5
                moisture_percent += 10

            # Simulate moisture loss
            moisture_percent -= 8  # Daily moisture loss
            moisture_percent = max(10, min(100, moisture_percent))

            schedule.append({
                'date': date.strftime('%Y-%m-%d'),
                'day': date.strftime('%A'),
                'recommendation': recommendation,
                'water_amount_mm': round(water_amount, 1) if water_amount > 0 else 0,
                'rain_expected': rain_expected,
                'rain_amount_mm': round(rain_amount, 1) if rain_expected else 0
            })

        return schedule

    def _get_crop_water_requirement(self, crop_type):
        """
        Return daily water requirement in mm for different crops
        """
        water_requirements = {
            'maize': 5.0,
            'corn': 5.0,
            'wheat': 4.0,
            'rice': 7.0,
            'soybean': 4.5,
            'tomato': 5.5,
            'potato': 5.0,
            'cotton': 5.5,
            'sugarcane': 6.0,
            'default': 5.0
        }

        return water_requirements.get(crop_type.lower() if crop_type else 'default', 5.0)