"""
Create initial platform owner account.

Usage:
  python scripts/create_initial_owner.py --email you@example.com --password secret
"""
import argparse
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import PlatformOwner


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        existing = db.query(PlatformOwner).filter(PlatformOwner.email == args.email).first()
        if existing:
            print("Owner already exists")
            return
        owner = PlatformOwner(email=args.email, password_hash=hash_password(args.password), is_active=True)
        db.add(owner)
        db.commit()
        print("Owner created")
    finally:
        db.close()


if __name__ == "__main__":
    main()
