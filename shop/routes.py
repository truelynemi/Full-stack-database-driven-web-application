# shop/routes.py
# ─────────────────────────────────────────────────────────────────────────────
# Customer-facing shop routes:
#   GET  /shop                        — product catalogue
#   GET  /shop/<id>                   — product detail page
#   GET  /cart                        — view cart
#   POST /cart/add/<id>               — add item to cart
#   POST /cart/remove/<id>            — remove item from cart
#   POST /checkout/create             — create Stripe Checkout Session
#   GET  /checkout/success            — Stripe redirects here after payment
#   GET  /checkout/cancel             — Stripe redirects here if user cancels
#   GET  /orders                      — user's order history
#
# Cart is stored in Flask's server-side session as:
#   session['cart'] = {'1': 2, '3': 1}   (str(product_id): quantity)
# ─────────────────────────────────────────────────────────────────────────────

import os

import stripe
from flask import render_template, redirect, url_for, flash, session, request
from flask_mail import Message

from models import db, Product, Order, OrderItem, User
from extensions import mail
from auth.helpers import login_required
from shop import shop_bp


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _send_receipt_email(order):
    """
    Send an HTML order receipt to the customer.
    Called after a successful Stripe payment and DB commit.
    Silently swallowed if mail fails — we never block the success page.
    """
    user = User.query.get(order.user_id)
    if not user:
        return

    html_body = render_template(
        'email/order_receipt.html',
        order=order,
        user=user,
        orders_url=url_for('shop.orders', _external=True),
    )

    msg = Message(
        subject=f'Your order receipt — Order #{order.id}',
        recipients=[user.email],
        html=html_body,
    )
    mail.send(msg)


def _get_cart():
    """Return the cart dict from the session, creating it if absent."""
    return session.setdefault('cart', {})


def _cart_count():
    """Total number of individual items in the cart (sum of all quantities)."""
    return sum(_get_cart().values())


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCT CATALOGUE  —  GET /shop
# ─────────────────────────────────────────────────────────────────────────────

@shop_bp.route('/shop')
@login_required
def catalogue():
    """Show all active products in a grid."""
    products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).all()
    return render_template('shop/catalogue.html', products=products, cart_count=_cart_count())


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCT DETAIL  —  GET /shop/<product_id>
# ─────────────────────────────────────────────────────────────────────────────

@shop_bp.route('/shop/<int:product_id>')
@login_required
def product_detail(product_id):
    """Show a single product's full details."""
    product = Product.query.get_or_404(product_id)
    if not product.is_active:
        flash('That product is not currently available.', 'warning')
        return redirect(url_for('shop.catalogue'))
    return render_template('shop/product.html', product=product, cart_count=_cart_count())


# ─────────────────────────────────────────────────────────────────────────────
# CART — GET /cart
# ─────────────────────────────────────────────────────────────────────────────

@shop_bp.route('/cart')
@login_required
def cart():
    """Show the contents of the cart with a subtotal and checkout button."""
    cart_data = _get_cart()

    # Load products for each cart entry
    cart_items = []
    subtotal = 0
    for product_id_str, qty in cart_data.items():
        product = Product.query.get(int(product_id_str))
        if product and product.is_active:
            cart_items.append({'product': product, 'quantity': qty, 'line_total': product.price * qty})
            subtotal += product.price * qty

    return render_template('shop/cart.html', cart_items=cart_items, subtotal=subtotal, cart_count=_cart_count())


# ─────────────────────────────────────────────────────────────────────────────
# ADD TO CART  —  POST /cart/add/<product_id>
# ─────────────────────────────────────────────────────────────────────────────

@shop_bp.route('/cart/add/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    """Increment the quantity of a product in the session cart."""
    product = Product.query.get_or_404(product_id)
    if not product.is_active:
        flash('That product is not available.', 'warning')
        return redirect(url_for('shop.catalogue'))

    cart = _get_cart()
    key = str(product_id)
    cart[key] = cart.get(key, 0) + 1
    session.modified = True  # Tell Flask the session has changed

    flash(f'"{product.name}" added to your cart.', 'success')
    # Go back to where the user came from (catalogue or product page)
    return redirect(request.referrer or url_for('shop.catalogue'))


# ─────────────────────────────────────────────────────────────────────────────
# REMOVE FROM CART  —  POST /cart/remove/<product_id>
# ─────────────────────────────────────────────────────────────────────────────

@shop_bp.route('/cart/remove/<int:product_id>', methods=['POST'])
@login_required
def remove_from_cart(product_id):
    """Remove a product entirely from the session cart."""
    cart = _get_cart()
    cart.pop(str(product_id), None)
    session.modified = True
    flash('Item removed from cart.', 'info')
    return redirect(url_for('shop.cart'))


# ─────────────────────────────────────────────────────────────────────────────
# CREATE CHECKOUT SESSION  —  POST /checkout/create
# ─────────────────────────────────────────────────────────────────────────────

@shop_bp.route('/checkout/create', methods=['POST'])
@login_required
def checkout_create():
    """
    Build the Stripe Checkout Session from the current cart and redirect the user
    to Stripe's hosted payment page.
    """
    cart_data = _get_cart()
    if not cart_data:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('shop.cart'))

    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

    # Build line_items list for Stripe
    line_items = []
    for product_id_str, qty in cart_data.items():
        product = Product.query.get(int(product_id_str))
        if product and product.is_active:
            item = {
                'price_data': {
                    'currency': 'gbp',
                    'product_data': {'name': product.name},
                    'unit_amount': product.price,  # already in pence
                },
                'quantity': qty,
            }
            line_items.append(item)

    if not line_items:
        flash('No valid items in cart.', 'warning')
        return redirect(url_for('shop.cart'))

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=url_for('shop.checkout_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('shop.checkout_cancel', _external=True),
            metadata={'user_id': session['user_id']},
        )
        return redirect(checkout_session.url, code=303)
    except stripe.error.StripeError as e:
        flash(f'Payment error: {e.user_message}', 'danger')
        return redirect(url_for('shop.cart'))


# ─────────────────────────────────────────────────────────────────────────────
# CHECKOUT SUCCESS  —  GET /checkout/success
# ─────────────────────────────────────────────────────────────────────────────

@shop_bp.route('/checkout/success')
@login_required
def checkout_success():
    """
    Stripe redirects the user here after a successful payment.
    We verify the payment with Stripe, save the Order to the database, and clear the cart.
    """
    session_id = request.args.get('session_id')
    if not session_id:
        return redirect(url_for('shop.catalogue'))

    stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

    try:
        checkout_session = stripe.checkout.Session.retrieve(
            session_id,
            expand=['line_items'],
        )
    except stripe.error.StripeError:
        flash('Could not verify payment. Please contact support.', 'danger')
        return redirect(url_for('shop.catalogue'))

    # Guard: only process paid sessions, and only once (idempotency)
    if checkout_session.payment_status != 'paid':
        flash('Payment was not completed.', 'warning')
        return redirect(url_for('shop.cart'))

    existing = Order.query.filter_by(stripe_checkout_session_id=session_id).first()
    if existing:
        # Already processed — show the same success page
        return render_template('shop/success.html', order=existing, cart_count=0)

    # Build and save the Order from the cart snapshot in the session
    cart_data = _get_cart()
    order = Order(
        user_id=session['user_id'],
        stripe_checkout_session_id=session_id,
        amount_total=checkout_session.amount_total,
        status='paid',
    )
    db.session.add(order)
    db.session.flush()  # Get order.id without committing yet

    for product_id_str, qty in cart_data.items():
        product = Product.query.get(int(product_id_str))
        if product:
            db.session.add(OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=qty,
                unit_price=product.price,
            ))

    db.session.commit()

    # Send receipt email — wrapped so a mail failure never breaks the checkout flow
    try:
        _send_receipt_email(order)
    except Exception:
        pass  # Log in production; silently skip for now

    # Clear the cart
    session.pop('cart', None)
    session.modified = True

    return render_template('shop/success.html', order=order, cart_count=0)


# ─────────────────────────────────────────────────────────────────────────────
# CHECKOUT CANCEL  —  GET /checkout/cancel
# ─────────────────────────────────────────────────────────────────────────────

@shop_bp.route('/checkout/cancel')
def checkout_cancel():
    """Stripe redirects here if the user cancels on the payment page."""
    return render_template('shop/cancel.html', cart_count=_cart_count())


# ─────────────────────────────────────────────────────────────────────────────
# ORDER HISTORY  —  GET /orders
# ─────────────────────────────────────────────────────────────────────────────

@shop_bp.route('/orders')
@login_required
def orders():
    """Show the current user's past orders."""
    user_orders = (
        Order.query
        .filter_by(user_id=session['user_id'])
        .order_by(Order.created_at.desc())
        .all()
    )
    return render_template('shop/orders.html', orders=user_orders, cart_count=_cart_count())
