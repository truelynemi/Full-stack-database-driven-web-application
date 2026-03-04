# shop/__init__.py
# Creates the Blueprint object for the shop feature.
# All customer-facing shop routes live in shop/routes.py.

from flask import Blueprint

shop_bp = Blueprint('shop', __name__)

from shop import routes  # noqa — must be imported after shop_bp is defined
