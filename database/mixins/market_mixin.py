"""Market, Prices, and Collection Center database operations"""
import json
from datetime import date


class MarketMixin:
    """Mixin for Market, Price, and Collection Center operations"""

    # ===== MARKET OPERATIONS =====

    def add_market(self, name, location=None, contact_phone=None,
                   contact_person=None, operating_days=None, payment_terms=None):
        """Add new market"""
        query = """
                INSERT INTO markets (name, location, contact_phone, contact_person,
                                     operating_days, payment_terms)
                VALUES (?, ?, ?, ?, ?, ?) \
                """
        return self.execute_write(
            query, (name, location, contact_phone, contact_person,
                    operating_days, payment_terms)
        )

    def get_all_markets(self, active_only=True):
        """Get all markets"""
        return self.generic_get_all('markets', active_only=active_only, order_by='name')

    def get_market(self, market_id):
        """Get single market by ID"""
        return self.generic_get_one('markets', market_id)

    def update_market(self, market_id, **kwargs):
        """Update market with any fields"""
        return self.generic_update('markets', market_id, **kwargs)

    def delete_market(self, market_id):
        """Soft delete market (set is_active = 0)"""
        return self.generic_soft_delete('markets', market_id)

    # ===== MARKET PRICE OPERATIONS =====

    def add_market_price(self, market_id, crop_type, price, unit='per 90kg bag',
                         grade=None, date_recorded=None, notes=None):
        """Add new market price"""
        if date_recorded is None:
            date_recorded = date.today().isoformat()

        with self.transaction() as conn:
            cursor = conn.cursor()

            # Mark previous prices as not current
            cursor.execute("""
                           UPDATE market_prices SET is_current = 0
                           WHERE market_id = ? AND crop_type = ? AND is_current = 1
                           """, (market_id, crop_type))

            # Insert new price
            cursor.execute("""
                           INSERT INTO market_prices (market_id, crop_type, price, unit,
                                                      grade, date_recorded, notes)
                           VALUES (?, ?, ?, ?, ?, ?, ?)
                           """, (market_id, crop_type, price, unit, grade, date_recorded, notes))

            return cursor.lastrowid

    def get_market_prices_by_crop(self, crop_type, current_only=True):
        """Get all prices for a specific crop"""
        if current_only:
            query = """
                    SELECT mp.*, m.name as market_name, m.location as market_location
                    FROM market_prices mp
                             JOIN markets m ON mp.market_id = m.id
                    WHERE mp.crop_type = ? AND mp.is_current = 1 AND m.is_active = 1
                    ORDER BY mp.price DESC \
                    """
        else:
            query = """
                    SELECT mp.*, m.name as market_name, m.location as market_location
                    FROM market_prices mp
                             JOIN markets m ON mp.market_id = m.id
                    WHERE mp.crop_type = ? AND m.is_active = 1
                    ORDER BY mp.date_recorded DESC \
                    """
        return self.execute_query(query, (crop_type,))

    def get_price_history(self, market_id, crop_type, days=30):
        """Get price history for a market and crop"""
        query = """
                SELECT * FROM market_prices
                WHERE market_id = ? AND crop_type = ?
                ORDER BY date_recorded DESC
                    LIMIT ? \
                """
        return self.execute_query(query, (market_id, crop_type, days))

    def update_market_price(self, price_id, **kwargs):
        """Update market price"""
        return self.generic_update('market_prices', price_id, **kwargs)

    def delete_market_price(self, price_id):
        """Delete market price"""
        return self.generic_delete('market_prices', price_id)

    # ===== COLLECTION CENTER OPERATIONS =====

    def add_collection_center(self, name, location=None, latitude=None,
                              longitude=None, crops_accepted=None, contact_phone=None,
                              contact_person=None, operating_days=None,
                              operating_hours=None, storage_capacity=None,
                              payment_terms=None, minimum_quantity=None,
                              quality_requirements=None):
        """Add new collection center"""
        crops_json = json.dumps(crops_accepted) if crops_accepted else None

        query = """
                INSERT INTO collection_centers (
                    name, location, latitude, longitude, crops_accepted,
                    contact_phone, contact_person, operating_days, operating_hours,
                    storage_capacity, payment_terms, minimum_quantity, quality_requirements
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) \
                """
        return self.execute_write(
            query, (name, location, latitude, longitude, crops_json, contact_phone,
                    contact_person, operating_days, operating_hours, storage_capacity,
                    payment_terms, minimum_quantity, quality_requirements)
        )

    def get_all_collection_centers(self, active_only=True):
        """Get all collection centers"""
        centers = self.generic_get_all('collection_centers', active_only=active_only)

        # Parse JSON crops_accepted
        for center in centers:
            if center.get('crops_accepted'):
                center['crops_accepted'] = json.loads(center['crops_accepted'])

        return centers

    def get_collection_center(self, center_id):
        """Get single collection center by ID"""
        center = self.generic_get_one('collection_centers', center_id)

        if center and center.get('crops_accepted'):
            center['crops_accepted'] = json.loads(center['crops_accepted'])

        return center

    def get_collection_centers_by_crop(self, crop_type, active_only=True):
        """Get collection centers that accept a specific crop"""
        centers = self.get_all_collection_centers(active_only)
        filtered = [
            c for c in centers
            if crop_type.lower() in [crop.lower() for crop in (c.get('crops_accepted') or [])]
        ]
        return filtered

    def update_collection_center(self, center_id, **kwargs):
        """Update collection center"""
        # Handle crops_accepted list
        if 'crops_accepted' in kwargs and isinstance(kwargs['crops_accepted'], list):
            kwargs['crops_accepted'] = json.dumps(kwargs['crops_accepted'])

        return self.generic_update('collection_centers', center_id, **kwargs)

    def delete_collection_center(self, center_id):
        """Soft delete collection center"""
        return self.generic_soft_delete('collection_centers', center_id)