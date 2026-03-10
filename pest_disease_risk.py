class PestDiseaseRiskAnalyzer:
    """Predict pest and disease risk based on weather, crop health, and season"""

    def assess_risk(self, crop_type, weather_data, health_data, moisture_data, location):
        """
        Assess pest and disease risk

        Returns:
            dict with risk assessments
        """
        risks = []

        crop_type = crop_type.lower()

        # Weather-based risks
        avg_temp = sum([day['temp'] for day in weather_data[:3]]) / 3
        avg_humidity = sum([day['humidity'] for day in weather_data[:3]]) / 3
        recent_rain = any([day['rain_mm'] > 5 for day in weather_data[:3]])

        # Maize-specific pests/diseases
        if crop_type == 'maize':
            # Fall Armyworm risk (high temp, dry conditions)
            if avg_temp > 27 and moisture_data['status'] in ['low', 'dry']:
                risks.append({
                    'pest_disease': 'Fall Armyworm',
                    'risk_level': 'high',
                    'probability': 75,
                    'symptoms': 'Holes in leaves, sawdust-like frass',
                    'action': 'Scout fields daily, apply pesticide if >5 plants/100 infested',
                    'critical_stage': ['Vegetative', 'Tasseling/Flowering']
                })

            # Maize Streak Virus (spread by leafhoppers in warm weather)
            if avg_temp > 25 and health_data['score'] < 60:
                risks.append({
                    'pest_disease': 'Maize Streak Virus',
                    'risk_level': 'medium',
                    'probability': 50,
                    'symptoms': 'Yellow streaks along leaf veins',
                    'action': 'Control leafhopper vectors, remove infected plants',
                    'prevention': 'Use resistant varieties, early planting'
                })

            # Gray Leaf Spot (high humidity, recent rain)
            if avg_humidity > 70 and recent_rain:
                risks.append({
                    'pest_disease': 'Gray Leaf Spot',
                    'risk_level': 'medium',
                    'probability': 60,
                    'symptoms': 'Rectangular gray lesions on leaves',
                    'action': 'Apply fungicide, improve field drainage',
                    'critical_stage': ['Tasseling/Flowering', 'Grain Filling']
                })

            # Stalk Borers
            risks.append({
                'pest_disease': 'Stalk Borers',
                'risk_level': 'low',
                'probability': 30,
                'symptoms': 'Dead heart, holes in stalk, frass',
                'action': 'Regular scouting, apply pesticide early',
                'prevention': 'Destroy crop residues, early planting'
            })

        # Sugarcane-specific pests/diseases
        elif crop_type == 'sugarcane':
            # Sugarcane Smut
            if recent_rain and avg_temp > 25:
                risks.append({
                    'pest_disease': 'Sugarcane Smut',
                    'risk_level': 'medium',
                    'probability': 45,
                    'symptoms': 'Black whip-like structure from growing point',
                    'action': 'Remove and burn infected plants',
                    'prevention': 'Use disease-free seed cane'
                })

            # Sugarcane Aphids
            if moisture_data['status'] in ['low', 'dry']:
                risks.append({
                    'pest_disease': 'Sugarcane Aphids',
                    'risk_level': 'low',
                    'probability': 35,
                    'symptoms': 'Honeydew on leaves, sooty mold',
                    'action': 'Monitor populations, natural enemies usually control',
                    'threshold': '>100 aphids per leaf'
                })

        # General stress-related issues
        if health_data['score'] < 50:
            risks.append({
                'pest_disease': 'Secondary Infections',
                'risk_level': 'high',
                'probability': 80,
                'symptoms': 'Weak plants susceptible to multiple issues',
                'action': 'Identify primary cause of stress, improve plant vigor',
                'note': 'Stressed plants are more vulnerable to pests and diseases'
            })

        # Sort by risk level
        risk_order = {'high': 0, 'medium': 1, 'low': 2}
        risks.sort(key=lambda x: risk_order.get(x['risk_level'], 3))

        return {
            'total_risks': len(risks),
            'high_risk_count': len([r for r in risks if r['risk_level'] == 'high']),
            'risks': risks,
            'recommendation': self._generate_overall_recommendation(risks)
        }

    def _generate_overall_recommendation(self, risks):
        """Generate overall pest/disease management recommendation"""
        high_risks = [r for r in risks if r['risk_level'] == 'high']

        if len(high_risks) > 0:
            return {
                'priority': 'urgent',
                'message': f'{len(high_risks)} high-risk pest/disease threat(s) detected. Immediate scouting required.',
                'action': 'Inspect fields within 24 hours and prepare control measures'
            }
        elif len(risks) > 0:
            return {
                'priority': 'moderate',
                'message': 'Some pest/disease risks present. Regular monitoring recommended.',
                'action': 'Scout fields 2-3 times per week'
            }
        else:
            return {
                'priority': 'low',
                'message': 'Low pest/disease pressure currently.',
                'action': 'Continue routine monitoring'
            }