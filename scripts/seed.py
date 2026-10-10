import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, seed_employees, create_user, get_user_by_username
from app.models import UserCreate


def main():
    print("Initializing database...")
    init_db()
    
    print("Seeding employees...")
    seed_employees()
    
    print("Creating demo users...")
    demo_users = [
        UserCreate(username="admin", password="admin123", role="admin"),
        UserCreate(username="hr", password="hr123", role="hr"),
        UserCreate(username="engineering", password="engineering123", role="engineering"),
        UserCreate(username="finance", password="finance123", role="finance"),
    ]
    
    for user_data in demo_users:
        existing = get_user_by_username(user_data.username)
        if not existing:
            create_user(user_data)
            print(f"  Created user: {user_data.username} ({user_data.role})")
        else:
            print(f"  User already exists: {user_data.username}")
    
    print("Database seeding complete!")


if __name__ == "__main__":
    main()