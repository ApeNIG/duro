"""
Sample Python code for eval testing.
This file contains intentional patterns for code review verification.
"""

import os
import json
from typing import Optional, List, Dict, Any


class UserService:
    """Service for managing user operations."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._cache: Dict[str, Any] = {}

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a user by ID."""
        if user_id in self._cache:
            return self._cache[user_id]

        # Load from database
        try:
            with open(self.db_path, 'r') as f:
                data = json.load(f)
                user = data.get('users', {}).get(user_id)
                if user:
                    self._cache[user_id] = user
                return user
        except FileNotFoundError:
            return None

    def create_user(self, name: str, email: str) -> Dict[str, Any]:
        """Create a new user."""
        import uuid

        user_id = str(uuid.uuid4())
        user = {
            'id': user_id,
            'name': name,
            'email': email,
            'created_at': self._get_timestamp()
        }

        self._save_user(user)
        self._cache[user_id] = user
        return user

    def _get_timestamp(self) -> str:
        """Get current ISO timestamp."""
        from datetime import datetime
        return datetime.utcnow().isoformat()

    def _save_user(self, user: Dict[str, Any]) -> None:
        """Save user to database."""
        try:
            with open(self.db_path, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {'users': {}}

        data['users'][user['id']] = user

        with open(self.db_path, 'w') as f:
            json.dump(data, f, indent=2)

    def list_users(self) -> List[Dict[str, Any]]:
        """List all users."""
        try:
            with open(self.db_path, 'r') as f:
                data = json.load(f)
                return list(data.get('users', {}).values())
        except FileNotFoundError:
            return []


def main():
    """Example usage."""
    service = UserService('/tmp/users.json')

    # Create a user
    user = service.create_user('John Doe', 'john@example.com')
    print(f"Created user: {user['id']}")

    # Retrieve user
    retrieved = service.get_user(user['id'])
    print(f"Retrieved: {retrieved['name']}")


if __name__ == '__main__':
    main()
