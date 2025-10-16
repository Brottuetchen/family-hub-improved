#!/usr/bin/env python3
"""
Create initial admin user for Family Hub
Run this script after setting up the database to create your first admin account
"""

import getpass
import sys
from sqlalchemy.orm import Session

from database import SessionLocal, init_db, User
from auth import get_password_hash


def create_admin_user():
    """Interactive script to create an admin user"""

    print("=" * 50)
    print("Family Hub - Admin User Creation")
    print("=" * 50)
    print()

    # Initialize database
    print("Initializing database...")
    init_db()
    print("✓ Database initialized")
    print()

    # Get user input
    print("Please provide admin user details:")
    print()

    username = input("Username: ").strip()
    if not username:
        print("Error: Username cannot be empty")
        sys.exit(1)

    email = input("Email: ").strip()
    if not email:
        print("Error: Email cannot be empty")
        sys.exit(1)

    full_name = input("Full Name (optional): ").strip()

    # Get password with confirmation
    while True:
        password = getpass.getpass("Password: ")
        if len(password) < 8:
            print("Error: Password must be at least 8 characters")
            continue

        password_confirm = getpass.getpass("Confirm Password: ")
        if password != password_confirm:
            print("Error: Passwords do not match")
            continue

        break

    print()

    # Create database session
    db: Session = SessionLocal()

    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"Error: User '{username}' already exists")
            sys.exit(1)

        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            print(f"Error: Email '{email}' already registered")
            sys.exit(1)

        # Create admin user
        print("Creating admin user...")
        admin_user = User(
            username=username,
            email=email,
            full_name=full_name if full_name else None,
            hashed_password=get_password_hash(password),
            is_active=True,
            is_admin=True
        )

        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        print()
        print("=" * 50)
        print("✓ Admin user created successfully!")
        print("=" * 50)
        print()
        print(f"Username: {admin_user.username}")
        print(f"Email: {admin_user.email}")
        print(f"Full Name: {admin_user.full_name or 'Not set'}")
        print(f"Admin: Yes")
        print()
        print("You can now log in with these credentials.")
        print()

    except Exception as e:
        print(f"Error creating admin user: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    create_admin_user()
