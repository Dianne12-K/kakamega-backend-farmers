import math
from datetime import date, timedelta


class MarketService:
    """Service layer for market data operations"""

    def __init__(self, database):
        self.db = database

    # ==================== MARKET OPERATIONS ====================

    def create_market(self, data):
        """Create a new market"""
        try:
            market_id = self.db.add_market(
                name=data['name'],
                location=data.get('location'),
                contact_phone=data.get('contact_phone'),
                contact_person=data.get('contact_person'),
                operating_days=data.get('operating_days'),
                payment_terms=data.get('payment_terms')
            )

            market = self.db.get_market(market_id)
            return {
                'success': True,
                'message': 'Market created successfully',
                'market': market
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error creating market: {str(e)}'
            }

    def get_all_markets(self, active_only=True):
        """Get all markets"""
        markets = self.db.get_all_markets(active_only)
        return {
            'success': True,
            'count': len(markets),
            'markets': markets
        }

    def get_market(self, market_id):
        """Get single market"""
        market = self.db.get_market(market_id)
        if not market:
            return {
                'success': False,
                'message': 'Market not found'
            }
        return {
            'success': True,
            'market': market
        }

    def update_market(self, market_id, data):
        """Update market"""
        try:
            success = self.db.update_market(market_id, **data)
            if not success:
                return {
                    'success': False,
                    'message': 'Market not found or no changes made'
                }

            market = self.db.get_market(market_id)
            return {
                'success': True,
                'message': 'Market updated successfully',
                'market': market
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error updating market: {str(e)}'
            }

    def delete_market(self, market_id):
        """Delete (deactivate) market"""
        try:
            success = self.db.delete_market(market_id)
            if not success:
                return {
                    'success': False,
                    'message': 'Market not found'
                }

            return {
                'success': True,
                'message': 'Market deactivated successfully'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error deleting market: {str(e)}'
            }

    # ==================== PRICE OPERATIONS ====================

    def create_price(self, data):
        """Create/update market price"""
        try:
            price_id = self.db.add_market_price(
                market_id=data['market_id'],
                crop_type=data['crop_type'],
                price=data['price'],
                unit=data.get('unit', 'per 90kg bag'),
                grade=data.get('grade'),
                date_recorded=data.get('date_recorded'),
                notes=data.get('notes')
            )

            return {
                'success': True,
                'message': 'Price created successfully',
                'price_id': price_id
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error creating price: {str(e)}'
            }

    def get_market_prices(self, crop_type, current_only=True):
        """Get current prices for a crop with analysis"""
        prices = self.db.get_market_prices_by_crop(crop_type, current_only)

        if not prices:
            return {
                'success': False,
                'message': f'No prices found for {crop_type}'
            }

        # Calculate summary statistics
        price_values = [p['price'] for p in prices]
        highest = max(price_values)
        lowest = min(price_values)
        average = sum(price_values) / len(price_values)

        # Find best market
        best_price = max(prices, key=lambda x: x['price'])

        return {
            'success': True,
            'crop': crop_type,
            'last_updated': prices[0]['date_recorded'],
            'count': len(prices),
            'prices': prices,
            'summary': {
                'highest_price': highest,
                'lowest_price': lowest,
                'average_price': round(average, 2),
                'best_market': best_price['market_name'],
                'best_price': best_price['price']
            },
            'recommendation': self._get_selling_recommendation(prices, average)
        }

    def get_price_history(self, market_id, crop_type, days=30):
        """Get price history"""
        prices = self.db.get_price_history(market_id, crop_type, days)
        return {
            'success': True,
            'count': len(prices),
            'history': prices
        }

    def update_price(self, price_id, data):
        """Update market price"""
        try:
            success = self.db.update_market_price(price_id, **data)
            if not success:
                return {
                    'success': False,
                    'message': 'Price not found or no changes made'
                }

            return {
                'success': True,
                'message': 'Price updated successfully'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error updating price: {str(e)}'
            }

    def delete_price(self, price_id):
        """Delete market price"""
        try:
            success = self.db.delete_market_price(price_id)
            if not success:
                return {
                    'success': False,
                    'message': 'Price not found'
                }

            return {
                'success': True,
                'message': 'Price deleted successfully'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error deleting price: {str(e)}'
            }

    def bulk_update_prices(self, crop_type, updates):
        """Bulk update prices for multiple markets"""
        try:
            results = []
            for update in updates:
                result = self.create_price({
                    'market_id': update['market_id'],
                    'crop_type': crop_type,
                    'price': update['price'],
                    'unit': update.get('unit', 'per 90kg bag'),
                    'grade': update.get('grade'),
                    'date_recorded': update.get('date_recorded')
                })
                results.append(result)

            return {
                'success': True,
                'message': f'Updated prices for {len(results)} markets',
                'results': results
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error in bulk update: {str(e)}'
            }

    # ==================== COLLECTION CENTER OPERATIONS ====================

    def create_collection_center(self, data):
        """Create new collection center"""
        try:
            center_id = self.db.add_collection_center(
                name=data['name'],
                location=data.get('location'),
                latitude=data.get('latitude'),
                longitude=data.get('longitude'),
                crops_accepted=data.get('crops_accepted', []),
                contact_phone=data.get('contact_phone'),
                contact_person=data.get('contact_person'),
                operating_days=data.get('operating_days'),
                operating_hours=data.get('operating_hours'),
                storage_capacity=data.get('storage_capacity'),
                payment_terms=data.get('payment_terms'),
                minimum_quantity=data.get('minimum_quantity'),
                quality_requirements=data.get('quality_requirements')
            )

            center = self.db.get_collection_center(center_id)
            return {
                'success': True,
                'message': 'Collection center created successfully',
                'center': center
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error creating collection center: {str(e)}'
            }

    def get_all_collection_centers(self, crop_type=None, farm_location=None, active_only=True):
        """Get collection centers with optional filtering"""
        if crop_type:
            centers = self.db.get_collection_centers_by_crop(crop_type, active_only)
        else:
            centers = self.db.get_all_collection_centers(active_only)

        # Calculate distances if farm location provided
        if farm_location and 'lat' in farm_location and 'lon' in farm_location:
            for center in centers:
                if center.get('latitude') and center.get('longitude'):
                    center['distance_km'] = self._calculate_distance(
                        farm_location['lat'], farm_location['lon'],
                        center['latitude'], center['longitude']
                    )

            # Sort by distance
            centers.sort(key=lambda x: x.get('distance_km', 999))

        return {
            'success': True,
            'count': len(centers),
            'centers': centers,
            'recommendation': self._get_collection_recommendation(centers)
        }

    def get_collection_center(self, center_id):
        """Get single collection center"""
        center = self.db.get_collection_center(center_id)
        if not center:
            return {
                'success': False,
                'message': 'Collection center not found'
            }
        return {
            'success': True,
            'center': center
        }

    def update_collection_center(self, center_id, data):
        """Update collection center"""
        try:
            success = self.db.update_collection_center(center_id, **data)
            if not success:
                return {
                    'success': False,
                    'message': 'Collection center not found or no changes made'
                }

            center = self.db.get_collection_center(center_id)
            return {
                'success': True,
                'message': 'Collection center updated successfully',
                'center': center
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error updating collection center: {str(e)}'
            }

    def delete_collection_center(self, center_id):
        """Delete (deactivate) collection center"""
        try:
            success = self.db.delete_collection_center(center_id)
            if not success:
                return {
                    'success': False,
                    'message': 'Collection center not found'
                }

            return {
                'success': True,
                'message': 'Collection center deactivated successfully'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error deleting collection center: {str(e)}'
            }

    # ==================== HELPER METHODS ====================

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in km using Haversine formula"""
        R = 6371  # Earth's radius in km

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) \
            * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return round(R * c, 1)

    def _get_selling_recommendation(self, prices, average):
        """Recommend best selling strategy"""
        if not prices:
            return "No price data available"

        best_price_obj = max(prices, key=lambda x: x['price'])

        if best_price_obj['price'] > average * 1.15:
            diff = best_price_obj['price'] - average
            return f"Consider selling at {best_price_obj['market_name']} for KES {diff:.0f} more per unit than average"
        else:
            return "Prices are similar across markets. Choose based on convenience and payment terms."

    def _get_collection_recommendation(self, centers):
        """Recommend best collection center"""
        if not centers:
            return "No collection centers found for this crop"

        if len(centers) == 1:
            return f"Deliver to {centers[0]['name']}"

        nearest = centers[0]
        distance_text = f" ({nearest.get('distance_km', 'N/A')} km away)" if 'distance_km' in nearest else ""
        return f"Nearest collection point: {nearest['name']}{distance_text}"