"""Sub-county and Ward database operations"""


class LocationMixin:
    """Mixin for Sub-county and Ward operations"""

    # ===== SUB-COUNTY OPERATIONS =====

    def get_all_subcounties(self):
        """Get all sub-counties"""
        return self.generic_get_all('subcounties', order_by='name')

    def get_subcounty(self, subcounty_id):
        """Get single sub-county by ID"""
        return self.generic_get_one('subcounties', subcounty_id)

    def add_subcounty(self, name, code='', description=''):
        """Add new sub-county"""
        query = """
                INSERT INTO subcounties (name, code, description)
                VALUES (?, ?, ?) \
                """
        return self.execute_write(query, (name, code, description))

    def update_subcounty(self, subcounty_id, name=None, code=None, description=None):
        """Update sub-county"""
        return self.generic_update(
            'subcounties', subcounty_id,
            name=name, code=code, description=description
        )

    def delete_subcounty(self, subcounty_id):
        """Delete sub-county"""
        return self.generic_delete('subcounties', subcounty_id)

    def get_ward_count_by_subcounty(self, subcounty_id):
        """Get count of wards in a sub-county"""
        result = self.execute_one(
            "SELECT COUNT(*) as count FROM wards WHERE subcounty_id = ?",
            (subcounty_id,)
        )
        return result['count'] if result else 0

    # ===== WARD OPERATIONS =====

    def get_all_wards(self):
        """Get all wards"""
        return self.generic_get_all('wards', order_by='name')

    def get_ward(self, ward_id):
        """Get single ward by ID"""
        return self.generic_get_one('wards', ward_id)

    def get_wards_by_subcounty(self, subcounty_id):
        """Get all wards in a sub-county"""
        return self.execute_query(
            "SELECT * FROM wards WHERE subcounty_id = ? ORDER BY name",
            (subcounty_id,)
        )

    def add_ward(self, name, subcounty_id, code='', population=0, area_sq_km=0):
        """Add new ward"""
        query = """
                INSERT INTO wards (name, subcounty_id, code, population, area_sq_km)
                VALUES (?, ?, ?, ?, ?) \
                """
        return self.execute_write(query, (name, subcounty_id, code, population, area_sq_km))

    def update_ward(self, ward_id, name=None, subcounty_id=None, code=None,
                    population=None, area_sq_km=None):
        """Update ward"""
        return self.generic_update(
            'wards', ward_id,
            name=name, subcounty_id=subcounty_id, code=code,
            population=population, area_sq_km=area_sq_km
        )

    def delete_ward(self, ward_id):
        """Delete ward"""
        return self.generic_delete('wards', ward_id)