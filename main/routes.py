# main/routes.py
# ─────────────────────────────────────────────────────────────────────────────
# Route handlers for all non-authentication pages:
#   GET       /about
#   GET       /user_dashboard
#   GET       /admin_dashboard
#   GET/POST  /profile
#
# All protected routes use the @login_required decorator from auth/helpers.py.
# ─────────────────────────────────────────────────────────────────────────────

import re  # Regex — used for password strength validation on the profile page

from flask import render_template, redirect, url_for, flash, session, request
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, Product, Order, OrderItem
from extensions import limiter
from auth.helpers import login_required
from auth.forms import ProfileForm
from main import main_bp


# ─────────────────────────────────────────────────────────────────────────────
# ABOUT PAGE  —  GET /about
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route('/about')
@limiter.exempt  # This page is public info — no need to rate-limit it
def about():
    """Public about page — no login required."""
    return render_template('main/about.html')


@main_bp.route('/privacy')
@limiter.exempt
def privacy():
    """Public privacy policy page."""
    return render_template('main/privacy.html')


@main_bp.route('/terms')
@limiter.exempt
def terms():
    """Public terms of service page."""
    return render_template('main/terms.html')


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD ROUTES
# These are the pages users land on after logging in.
# Both are protected by @login_required — unauthenticated users are redirected
# to /login before they can see any content.
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route('/user_dashboard')
@login_required  # Must be logged in to access this page
def user_dashboard():
    """Standard user dashboard — shown to any logged-in, non-admin user."""
    return render_template('main/user_dashboard.html')


@main_bp.route('/admin_dashboard')
@login_required  # Must be logged in first...
def admin_dashboard():
    """Admin dashboard — only accessible to users with role='admin'."""
    if session.get('user_role') != 'admin':
        # Logged in but not an admin — redirect with a warning
        flash('You do not have permission to access that page.', 'danger')
        return redirect(url_for('main.user_dashboard'))
    return render_template('main/admin_dashboard.html')


# ─────────────────────────────────────────────────────────────────────────────
# PROFILE ROUTE  —  GET/POST /profile
# Lets a logged-in user update their name and optionally change their password.
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required  # Must be logged in — unauthenticated users go to /login
def profile():
    # Look up the current user in the database using their session ID
    user = User.query.get(session['user_id'])

    # Pre-fill first/last name by splitting the stored full_name on the first space
    # e.g. "John Smith" → first="John", last="Smith"
    name_parts = user.full_name.split(' ', 1)
    first = name_parts[0]
    last  = name_parts[1] if len(name_parts) > 1 else ''

    form = ProfileForm()
    error = None

    if form.validate_on_submit():
        # ── Update name ───────────────────────────────────────────────────
        new_first = form.first_name.data.strip()
        new_last  = form.last_name.data.strip()
        user.full_name = f"{new_first} {new_last}"

        # Update the session so the dashboard greeting reflects the new name immediately
        session['user_name'] = user.full_name

        # ── Optional password change ──────────────────────────────────────
        new_password = form.new_password.data
        if new_password:
            current_password     = form.current_password.data
            confirm_new_password = form.confirm_new_password.data

            # Step 1: Verify the user knows their current password
            if not current_password or not check_password_hash(user.password_hash, current_password):
                error = "Current password is incorrect."
            elif new_password != confirm_new_password:
                error = "New passwords do not match."
            elif len(new_password) < 8:
                error = "New password must be at least 8 characters long."
            elif not re.search(r"\d", new_password):
                error = "New password must include at least one number."
            elif not re.search(r"[A-Z]", new_password):
                error = "New password must include at least one uppercase letter."
            else:
                # All checks pass — hash and save the new password
                user.password_hash = generate_password_hash(new_password)

        if not error:
            db.session.commit()  # Save name (and password if changed) to the database
            flash("Profile updated successfully.", "success")
            return redirect(url_for('main.profile'))

    elif request.method == 'GET':
        # On a GET request, pre-fill the name fields with the current values
        form.first_name.data = first
        form.last_name.data  = last

    return render_template('main/profile.html', form=form, error=error)


# ─────────────────────────────────────────────────────────────────────────────
# ACCOUNT DELETION  —  POST /account/delete
# Permanently removes the logged-in user's account and all their orders.
# Requires password confirmation so this can't be triggered by a stray link.
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route('/account/delete', methods=['POST'])
@login_required
def account_delete():
    """Permanently delete the current user's account and all their data."""
    user = User.query.get_or_404(session['user_id'])
    password = request.form.get('password', '')

    # Verify the user knows their own password before we destroy anything
    if not check_password_hash(user.password_hash, password):
        flash('Incorrect password. Your account was not deleted.', 'danger')
        return redirect(url_for('main.profile'))

    # Delete order items first (child FK), then orders (parent FK), then the user.
    # SQLite doesn't enforce FK cascades by default so we delete manually.
    for order in user.orders:
        for item in order.items:
            db.session.delete(item)
        db.session.delete(order)
    db.session.delete(user)
    db.session.commit()

    # Clear the session so the cookie no longer points to a deleted user
    session.clear()
    flash('Your account has been permanently deleted.', 'info')
    return redirect(url_for('auth.login'))


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN PRODUCT MANAGEMENT
# All routes below are admin-only.  They check session['user_role'] == 'admin'
# and redirect non-admins to their dashboard.
# ─────────────────────────────────────────────────────────────────────────────

def _admin_only():
    """Return a redirect response if the current user is not an admin, else None."""
    if session.get('user_role') != 'admin':
        flash('You do not have permission to access that page.', 'danger')
        return redirect(url_for('main.user_dashboard'))
    return None


@main_bp.route('/admin/products')
@login_required
def admin_products():
    """List all products (active and inactive) for admin management."""
    guard = _admin_only()
    if guard:
        return guard
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('admin/products.html', products=products)


@main_bp.route('/admin/products/new', methods=['GET', 'POST'])
@login_required
def admin_product_new():
    """Form to create a new product."""
    guard = _admin_only()
    if guard:
        return guard

    error = None
    if request.method == 'POST':
        name        = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price_str   = request.form.get('price', '').strip()
        image_url   = request.form.get('image_url', '').strip() or None
        is_active   = request.form.get('is_active') == 'on'

        if not name or not description or not price_str:
            error = 'Name, description, and price are required.'
        else:
            try:
                # Price entered in pounds (e.g. 9.99), stored as pence (999)
                price_pence = int(round(float(price_str) * 100))
                if price_pence <= 0:
                    raise ValueError
            except ValueError:
                error = 'Enter a valid price in pounds (e.g. 9.99).'

        if not error:
            product = Product(
                name=name,
                description=description,
                price=price_pence,
                image_url=image_url,
                is_active=is_active,
            )
            db.session.add(product)
            db.session.commit()
            flash(f'Product "{name}" created.', 'success')
            return redirect(url_for('main.admin_products'))

    return render_template('admin/product_form.html', product=None, error=error, action='new')


@main_bp.route('/admin/products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_product_edit(product_id):
    """Form to edit an existing product."""
    guard = _admin_only()
    if guard:
        return guard

    product = Product.query.get_or_404(product_id)
    error = None

    if request.method == 'POST':
        name        = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price_str   = request.form.get('price', '').strip()
        image_url   = request.form.get('image_url', '').strip() or None
        is_active   = request.form.get('is_active') == 'on'

        if not name or not description or not price_str:
            error = 'Name, description, and price are required.'
        else:
            try:
                price_pence = int(round(float(price_str) * 100))
                if price_pence <= 0:
                    raise ValueError
            except ValueError:
                error = 'Enter a valid price in pounds (e.g. 9.99).'

        if not error:
            product.name        = name
            product.description = description
            product.price       = price_pence
            product.image_url   = image_url
            product.is_active   = is_active
            db.session.commit()
            flash(f'Product "{name}" updated.', 'success')
            return redirect(url_for('main.admin_products'))

    return render_template('admin/product_form.html', product=product, error=error, action='edit')


@main_bp.route('/admin/products/<int:product_id>/delete', methods=['POST'])
@login_required
def admin_product_delete(product_id):
    """Delete a product. Uses POST to prevent accidental deletion via link."""
    guard = _admin_only()
    if guard:
        return guard

    product = Product.query.get_or_404(product_id)

    # Guard: if any orders reference this product, block the hard delete.
    # Deleting it would leave order_items rows pointing to a missing product,
    # which breaks the /orders page. Admins should deactivate instead.
    if product.items:
        flash(
            f'Cannot delete "{product.name}" — it has existing orders. '
            'Deactivate it instead by unchecking "Active" in the edit form.',
            'danger'
        )
        return redirect(url_for('main.admin_products'))

    name = product.name
    db.session.delete(product)
    db.session.commit()
    flash(f'Product "{name}" deleted.', 'info')
    return redirect(url_for('main.admin_products'))
