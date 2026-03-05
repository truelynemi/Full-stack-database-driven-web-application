# seed.py
# ─────────────────────────────────────────────────────────────────────────────
# Populates the database with the admin and test user accounts.
#
# Run once after first setup:
#   python seed.py
#
# Safe to run multiple times — existing rows are skipped, nothing is duplicated.
#
# Note: products are intentionally not seeded here. Add them through the
# admin panel (Admin Dashboard → Products → Add Product).
# ─────────────────────────────────────────────────────────────────────────────

from dotenv import load_dotenv
load_dotenv()

from app import app
from models import db, User
from werkzeug.security import generate_password_hash


ADMIN = {
    'full_name': 'Admin User',
    'email':     'admin@admin.com',
    'password':  'Admin1234',
    'role':      'admin',
}

TEST_USER = {
    'full_name': 'Test User',
    'email':     'user@test.com',
    'password':  'User1234',
    'role':      'user',
}


def seed_user(data):
    existing = User.query.filter_by(email=data['email']).first()
    if existing:
        print(f"  [skip] User already exists: {data['email']}")
        return
    user = User(
        full_name     = data['full_name'],
        email         = data['email'],
        password_hash = generate_password_hash(data['password']),
        role          = data['role'],
        is_verified   = True,   # Pre-verified so login works immediately
    )
    db.session.add(user)
    print(f"  [ok]   Created {data['role']}: {data['email']} / {data['password']}")


def main():
    with app.app_context():
        db.create_all()
        print("\nSeeding users...")
        seed_user(ADMIN)
        seed_user(TEST_USER)
        db.session.commit()
        print("\nDone. Database is ready.\n")
        print("  Admin login:  admin@admin.com  /  Admin1234")
        print("  User login:   user@test.com    /  User1234\n")


if __name__ == '__main__':
    main()
