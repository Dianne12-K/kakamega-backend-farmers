"""Generic helper methods to reduce CRUD code duplication"""


class CRUDHelpers:
    """Mixin providing generic CRUD operations"""

    def generic_update(self, table, record_id, **kwargs):
        """
        Generic update method for any table

        Args:
            table: Table name
            record_id: ID of record to update
            **kwargs: Field names and values to update

        Returns:
            bool: True if rows were affected
        """
        updates = []
        params = []

        for key, value in kwargs.items():
            if value is not None:
                updates.append(f"{key} = ?")
                params.append(value)

        if not updates:
            return False

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(record_id)

        query = f"UPDATE {table} SET {', '.join(updates)} WHERE id = ?"
        rows_affected = self.execute_write(query, tuple(params))

        return rows_affected > 0

    def generic_delete(self, table, record_id):
        """
        Generic hard delete for any table

        Args:
            table: Table name
            record_id: ID of record to delete

        Returns:
            bool: True if rows were affected
        """
        query = f"DELETE FROM {table} WHERE id = ?"
        rows_affected = self.execute_write(query, (record_id,))
        return rows_affected > 0

    def generic_soft_delete(self, table, record_id):
        """
        Generic soft delete (set is_active = 0)

        Args:
            table: Table name
            record_id: ID of record to soft delete

        Returns:
            bool: True if rows were affected
        """
        query = f"UPDATE {table} SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        rows_affected = self.execute_write(query, (record_id,))
        return rows_affected > 0

    def generic_get_all(self, table, active_only=False, order_by='name'):
        """
        Generic get all records from a table

        Args:
            table: Table name
            active_only: Filter by is_active = 1
            order_by: Field to order by

        Returns:
            list: List of records as dicts
        """
        query = f"SELECT * FROM {table}"
        if active_only:
            query += " WHERE is_active = 1"
        query += f" ORDER BY {order_by}"

        return self.execute_query(query)

    def generic_get_one(self, table, record_id):
        """
        Generic get single record by ID

        Args:
            table: Table name
            record_id: ID of record

        Returns:
            dict or None: Record as dict
        """
        query = f"SELECT * FROM {table} WHERE id = ?"
        return self.execute_one(query, (record_id,))