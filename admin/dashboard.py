# admin/dashboard.py
# ─────────────────────────────────────────────────────────────────────────────
# Admin dashboard — the landing page for admin users after login.
#
#   GET  /admin_dashboard  — admin home with quick-action cards
# ─────────────────────────────────────────────────────────────────────────────

from flask import render_template, redirect, url_for, flash, session

from auth.helpers import login_required
from admin import admin_bp


@admin_bp.route('/admin_dashboard')
@login_required
def admin_dashboard():
    """Admin dashboard — only accessible to users with role='admin'."""
    if session.get('user_role') != 'admin':
        flash('You do not have permission to access that page.', 'danger')
        return redirect(url_for('main.user_dashboard'))
    return render_template('admin/admin_dashboard.html')
