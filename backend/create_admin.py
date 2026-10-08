"""
Create an admin user in the database.

Run from the project root:
    python backend/create_admin.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import hash_password
from backend.app.models import User, UserProfile


def create_admin_user(email: str, password: str):
    """Create an admin user with the given email and password."""
    engine = create_engine(str(settings.DATABASE_URL))
    
    with Session(engine) as db:
        # Check if user already exists
        existing_user = db.scalar(
            select(User).where(User.email == email.lower())
        )
        
        if existing_user:
            print(f"User {email} already exists. Updating to admin...")
            existing_user.is_admin = True
            existing_user.password_hash = hash_password(password)
            existing_user.is_verified = True
            existing_user.is_active = True
            db.commit()
            print(f"Updated user {email} to admin with new password.")
        else:
            # Create new admin user
            user = User(
                email=email.lower(),
                password_hash=hash_password(password),
                first_name="Admin",
                last_name="User",
                is_admin=True,
                is_verified=True,
                is_active=True,
            )
            db.add(user)
            db.flush()  # Flush to get the user ID
            
            # Create empty profile
            profile = UserProfile(user_id=user.id)
            db.add(profile)
            
            db.commit()
            print(f"Created admin user: {email}")
        
        print(f"\nAdmin User Details:")
        print(f"Email: {email}")
        print(f"Password: {password}")
        print(f"Is Admin: True")
        print(f"Is Verified: True")
        print(f"Is Active: True")


if __name__ == "__main__":
    email = "admin@applyxai.com"
    password = "Shiva@19881988"
    
    print("Creating admin user...")
    create_admin_user(email, password)
    print("\nAdmin user created successfully!")
