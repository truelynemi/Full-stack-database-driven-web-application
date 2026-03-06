# admin/products.py
# ─────────────────────────────────────────────────────────────────────────────
# Admin product management routes.
#
#   GET       /admin/products          — list all products
#   GET/POST  /admin/products/new      — create a product
#   GET/POST  /admin/products/<id>/edit    — edit a product
#   POST      /admin/products/<id>/delete  — delete a product
# ─────────────────────────────────────────────────────────────────────────────

from flask import render_template, redirect, url_for, flash, session, request

from models import db, Product
from auth.helpers import login_required
from admin import admin_bp


def _admin_only():
    if session.get('user_role') != 'admin':
        flash('You do not have permission to access that page.', 'danger')
        return redirect(url_for('main.user_dashboard'))
    return None


@admin_bp.route('/admin/products')
@login_required
def admin_products():
    """List all products (active and inactive) for admin management."""
    guard = _admin_only()
    if guard:
        return guard
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('admin/products.html', products=products)


@admin_bp.route('/admin/products/new', methods=['GET', 'POST'])
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
            return redirect(url_for('admin.admin_products'))

    return render_template('admin/product_form.html', product=None, error=error, action='new')


@admin_bp.route('/admin/products/<int:product_id>/edit', methods=['GET', 'POST'])
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
            return redirect(url_for('admin.admin_products'))

    return render_template('admin/product_form.html', product=product, error=error, action='edit')


@admin_bp.route('/admin/products/<int:product_id>/delete', methods=['POST'])
@login_required
def admin_product_delete(product_id):
    """Delete a product."""
    guard = _admin_only()
    if guard:
        return guard

    product = Product.query.get_or_404(product_id)

    if product.items:
        flash(
            f'Cannot delete "{product.name}" — it has existing orders. '
            'Deactivate it instead by unchecking "Active" in the edit form.',
            'danger'
        )
        return redirect(url_for('admin.admin_products'))

    name = product.name
    db.session.delete(product)
    db.session.commit()
    flash(f'Product "{name}" deleted.', 'info')
    return redirect(url_for('admin.admin_products'))
