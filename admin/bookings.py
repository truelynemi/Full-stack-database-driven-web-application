# admin/bookings.py
# ─────────────────────────────────────────────────────────────────────────────
# Admin booking management routes.
#
#   GET       /admin/services                    — list all services
#   GET/POST  /admin/services/new                — create a service
#   GET/POST  /admin/services/<id>/edit          — edit a service
#   POST      /admin/services/<id>/delete        — delete a service
#   GET/POST  /admin/services/<id>/slots/new     — add a time slot
#   POST      /admin/slots/<id>/delete           — delete a slot
#   GET       /admin/bookings                    — view all bookings
# ─────────────────────────────────────────────────────────────────────────────

from datetime import datetime

from flask import render_template, redirect, url_for, flash, session, request

from models import db, BookableService, TimeSlot, Booking
from auth.helpers import login_required
from admin import admin_bp


def _admin_only():
    if session.get('user_role') != 'admin':
        flash('You do not have permission to access that page.', 'danger')
        return redirect(url_for('main.user_dashboard'))
    return None


def _confirmed_count(slot_id):
    return Booking.query.filter_by(slot_id=slot_id, status='confirmed').count()


@admin_bp.route('/admin/services')
@login_required
def admin_services():
    """List all bookable services (active and inactive) for admin management."""
    guard = _admin_only()
    if guard:
        return guard
    services = BookableService.query.order_by(BookableService.created_at.desc()).all()
    return render_template('admin/services.html', services=services)


@admin_bp.route('/admin/services/new', methods=['GET', 'POST'])
@login_required
def admin_service_new():
    """Form to create a new bookable service."""
    guard = _admin_only()
    if guard:
        return guard

    error = None
    if request.method == 'POST':
        name        = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip() or None
        is_active   = request.form.get('is_active') == 'on'

        if not name:
            error = 'Service name is required.'
        else:
            service = BookableService(name=name, description=description, is_active=is_active)
            db.session.add(service)
            db.session.commit()
            flash(f'Service "{name}" created.', 'success')
            return redirect(url_for('admin.admin_services'))

    return render_template('admin/service_form.html', service=None, error=error, action='new')


@admin_bp.route('/admin/services/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_service_edit(service_id):
    """Form to edit an existing bookable service."""
    guard = _admin_only()
    if guard:
        return guard

    service = BookableService.query.get_or_404(service_id)
    error = None

    if request.method == 'POST':
        name        = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip() or None
        is_active   = request.form.get('is_active') == 'on'

        if not name:
            error = 'Service name is required.'
        else:
            service.name        = name
            service.description = description
            service.is_active   = is_active
            db.session.commit()
            flash(f'Service "{name}" updated.', 'success')
            return redirect(url_for('admin.admin_services'))

    return render_template('admin/service_form.html', service=service, error=error, action='edit')


@admin_bp.route('/admin/services/<int:service_id>/delete', methods=['POST'])
@login_required
def admin_service_delete(service_id):
    """Delete a bookable service. Blocked if the service has any time slots."""
    guard = _admin_only()
    if guard:
        return guard

    service = BookableService.query.get_or_404(service_id)

    if service.slots:
        flash(
            f'Cannot delete "{service.name}" — it has existing time slots. '
            'Delete all slots first, or deactivate the service instead.',
            'danger'
        )
        return redirect(url_for('admin.admin_services'))

    name = service.name
    db.session.delete(service)
    db.session.commit()
    flash(f'Service "{name}" deleted.', 'info')
    return redirect(url_for('admin.admin_services'))


@admin_bp.route('/admin/services/<int:service_id>/slots/new', methods=['GET', 'POST'])
@login_required
def admin_slot_new(service_id):
    """Add a time slot to a bookable service."""
    guard = _admin_only()
    if guard:
        return guard

    service = BookableService.query.get_or_404(service_id)
    error = None

    if request.method == 'POST':
        date_str     = request.form.get('date', '').strip()
        start_str    = request.form.get('start_time', '').strip()
        end_str      = request.form.get('end_time', '').strip()
        capacity_str = request.form.get('capacity', '1').strip()

        if not date_str or not start_str or not end_str:
            error = 'Date, start time, and end time are required.'
        else:
            try:
                slot_date  = datetime.strptime(date_str, '%Y-%m-%d').date()
                start_time = datetime.strptime(start_str, '%H:%M').time()
                end_time   = datetime.strptime(end_str, '%H:%M').time()
            except ValueError:
                error = 'Invalid date or time format.'

            if not error and end_time <= start_time:
                error = 'End time must be after start time.'

            try:
                capacity = int(capacity_str)
                if capacity < 1:
                    raise ValueError
            except ValueError:
                error = 'Capacity must be a whole number of at least 1.'

        if not error:
            slot = TimeSlot(
                service_id=service_id,
                date=slot_date,
                start_time=start_time,
                end_time=end_time,
                capacity=capacity,
            )
            db.session.add(slot)
            db.session.commit()
            flash(f'Slot added for {slot_date.strftime("%d %b %Y")} at {start_str}.', 'success')
            return redirect(url_for('admin.admin_services'))

    return render_template('admin/slot_form.html', service=service, error=error)


@admin_bp.route('/admin/slots/<int:slot_id>/delete', methods=['POST'])
@login_required
def admin_slot_delete(slot_id):
    """Delete a time slot. Blocked if any confirmed bookings exist for it."""
    guard = _admin_only()
    if guard:
        return guard

    slot = TimeSlot.query.get_or_404(slot_id)

    confirmed = _confirmed_count(slot_id)
    if confirmed > 0:
        flash(
            f'Cannot delete that slot — it has {confirmed} confirmed booking(s). '
            'Cancel those bookings first.',
            'danger'
        )
        return redirect(url_for('admin.admin_services'))

    db.session.delete(slot)
    db.session.commit()
    flash('Time slot deleted.', 'info')
    return redirect(url_for('admin.admin_services'))


@admin_bp.route('/admin/bookings')
@login_required
def admin_all_bookings():
    """Read-only view of every booking across all services."""
    guard = _admin_only()
    if guard:
        return guard

    bookings = (
        Booking.query
        .order_by(Booking.created_at.desc())
        .all()
    )
    return render_template('admin/all_bookings.html', bookings=bookings)
