#!/usr/bin/env python3
"""
Add new user to Family Hub
"""

import sys
from sqlalchemy.orm import Session
from database import SessionLocal, User
from auth import get_password_hash

def add_user():
    username = input("Username: ").strip()
    email = input("Email: ").strip()
    full_name = input("Full Name: ").strip()
    password = input("Password: ").strip()
    is_admin = input("Admin? (y/n): ").lower() == 'y'

    db: Session = SessionLocal()
    
    try:
        # Check if user exists
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"Error: User '{username}' already exists")
            return
        
        # Create user
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            is_active=True,
            is_admin=is_admin
        )
        
        db.add(user)
        db.commit()
        
        print(f"\n✓ User '{username}' created successfully!")
        print(f"  Email: {email}")
        print(f"  Admin: {'Yes' if is_admin else 'No'}")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_user()
