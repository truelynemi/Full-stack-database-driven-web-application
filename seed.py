# seed.py
# ─────────────────────────────────────────────────────────────────────────────
# Populates the database with demo data for exam / presentation purposes.
#
# Run once before the demo:
#   python seed.py
#
# Safe to run multiple times — existing rows are skipped, nothing is duplicated.
# ─────────────────────────────────────────────────────────────────────────────

from dotenv import load_dotenv
load_dotenv()

from app import app
from models import db, User, Product
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

PRODUCTS = [
    {
        'name':        'Mechanical Keyboard',
        'description': 'A full-size mechanical keyboard with tactile switches. '
                       'Perfect for long coding sessions.',
        'price':       7999,   # £79.99
        'image_url':   'https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=400',
        'is_active':   True,
    },
    {
        'name':        'Wireless Mouse',
        'description': 'Ergonomic wireless mouse with a long-lasting battery and '
                       'precision optical sensor.',
        'price':       3499,   # £34.99
        'image_url':   'https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=400',
        'is_active':   True,
    },
    {
        'name':        'USB-C Hub',
        'description': '7-in-1 USB-C hub with HDMI, USB 3.0 ports, SD card reader, '
                       'and 100W pass-through charging.',
        'price':       4999,   # £49.99
        'image_url':   'https://images.unsplash.com/photo-1625842268584-8f3296236761?w=400',
        'is_active':   True,
    },
    {
        'name':        'Monitor Stand',
        'description': 'Adjustable aluminium monitor stand with a built-in storage '
                       'drawer. Raises your screen to eye level.',
        'price':       2999,   # £29.99
        'image_url':   'https://images.unsplash.com/photo-1547082299-de196ea013d6?w=400',
        'is_active':   True,
    },
    {
        'name':        'Webcam 1080p',
        'description': 'Full HD webcam with built-in microphone and auto-focus. '
                       'Plug-and-play, no drivers needed.',
        'price':       5999,   # £59.99
        'image_url':   'https://images.unsplash.com/photo-1587826080692-f439cd0b70da?w=400',
        'is_active':   False,  # Intentionally inactive — demonstrates the admin panel feature
    },
]


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


def seed_products():
    if Product.query.count() > 0:
        print(f"  [skip] Products already exist ({Product.query.count()} rows)")
        return
    for p in PRODUCTS:
        db.session.add(Product(**p))
        status = 'active' if p['is_active'] else 'inactive'
        print(f"  [ok]   Created product ({status}): {p['name']} — £{p['price'] / 100:.2f}")


def main():
    with app.app_context():
        db.create_all()
        print("\nSeeding users...")
        seed_user(ADMIN)
        seed_user(TEST_USER)
        print("\nSeeding products...")
        seed_products()
        db.session.commit()
        print("\nDone. Database is ready.\n")
        print("  Admin login:  admin@admin.com  /  Admin1234")
        print("  User login:   user@test.com    /  User1234\n")


if __name__ == '__main__':
    main()
