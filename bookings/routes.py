# bookings/routes.py
# ─────────────────────────────────────────────────────────────────────────────
# Generic booking system — users search available slots and reserve them.
# Admin creates bookable services and time slots via the admin panel.
#
# User-facing routes:
#   GET  /bookings                            — search / browse services
#   GET  /bookings/<service_id>               — service detail + slot list
#   POST /bookings/<slot_id>/book             — create a booking
#   GET  /bookings/my                         — user's own bookings
#   POST /bookings/<booking_id>/cancel        — cancel a booking
#
# Admin routes (login_required + admin role):
#   GET       /admin/services                         — list all services
#   GET/POST  /admin/services/new                     — create a service
#   GET/POST  /admin/services/<id>/edit               — edit a service
#   POST      /admin/services/<id>/delete             — delete service
#   GET/POST  /admin/services/<id>/slots/new          — add a time slot
#   POST      /admin/slots/<id>/delete                — delete a slot
#   GET       /admin/bookings                         — view all bookings
# ─────────────────────────────────────────────────────────────────────────────

from datetime import date as date_type, datetime

from flask import render_template, redirect, url_for, flash, session, request

from models import db, BookableService, TimeSlot, Booking, User
from auth.helpers import login_required
from bookings import bookings_bp


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _admin_only():
    """Return a redirect if the current user is not an admin, else None."""
    if session.get('user_role') != 'admin':
        flash('You do not have permission to access that page.', 'danger')
        return redirect(url_for('main.user_dashboard'))
    return None


def _confirmed_count(slot_id):
    """Count confirmed (non-cancelled) bookings for a given slot."""
    return Booking.query.filter_by(slot_id=slot_id, status='confirmed').count()


# ─────────────────────────────────────────────────────────────────────────────
# SEARCH  —  GET /bookings
# ─────────────────────────────────────────────────────────────────────────────

@bookings_bp.route('/bookings')
@login_required
def search():
    """
    Landing page: show all active services.
    Optionally filter by date (query param ?date=YYYY-MM-DD) to see
    only services that have available slots on that day.
    """
    date_str = request.args.get('date', '')
    filter_date = None
    if date_str:
        try:
            filter_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format. Use YYYY-MM-DD.', 'warning')

    services = BookableService.query.filter_by(is_active=True).order_by(BookableService.name).all()

    # If a date filter is given, only keep services that have at least one
    # available (not full) slot on that date
    if filter_date:
        def has_available_slot(service):
            for slot in service.slots:
                if slot.date == filter_date and _confirmed_count(slot.id) < slot.capacity:
                    return True
            return False
        services = [s for s in services if has_available_slot(s)]

    return render_template('bookings/search.html',
                           services=services,
                           filter_date=filter_date,
                           today=date_type.today())


# ─────────────────────────────────────────────────────────────────────────────
# SERVICE DETAIL  —  GET /bookings/<service_id>
# ─────────────────────────────────────────────────────────────────────────────

@bookings_bp.route('/bookings/<int:service_id>')
@login_required
def detail(service_id):
    """Show a service's upcoming slots with availability status."""
    service = BookableService.query.get_or_404(service_id)
    if not service.is_active:
        flash('That service is not currently available.', 'warning')
        return redirect(url_for('bookings.search'))

    today = date_type.today()

    # Only show future slots, sorted chronologically
    upcoming_slots = [
        s for s in service.slots
        if s.date >= today
    ]
    upcoming_slots.sort(key=lambda s: (s.date, s.start_time))

    # For each slot, compute how many confirmed bookings exist and whether
    # the current user already has one
    user_id = session['user_id']
    slot_info = []
    for slot in upcoming_slots:
        count = _confirmed_count(slot.id)
        user_booked = Booking.query.filter_by(
            slot_id=slot.id, user_id=user_id, status='confirmed'
        ).first() is not None
        slot_info.append({
            'slot': slot,
            'confirmed_count': count,
            'is_full': count >= slot.capacity,
            'user_booked': user_booked,
            'spaces_left': slot.capacity - count,
        })

    return render_template('bookings/detail.html',
                           service=service,
                           slot_info=slot_info)


# ─────────────────────────────────────────────────────────────────────────────
# BOOK A SLOT  —  POST /bookings/<slot_id>/book
# ─────────────────────────────────────────────────────────────────────────────

@bookings_bp.route('/bookings/<int:slot_id>/book', methods=['POST'])
@login_required
def book(slot_id):
    """
    Create a booking for the given slot.
    Guards against:
      1. Slot not found / service inactive
      2. Slot is in the past
      3. Slot is at capacity (fully booked)
      4. User already has a confirmed booking for this slot
    """
    slot = TimeSlot.query.get_or_404(slot_id)

    # Guard: service must be active
    if not slot.service.is_active:
        flash('That service is no longer available.', 'danger')
        return redirect(url_for('bookings.search'))

    # Guard: slot must be in the future
    if slot.date < date_type.today():
        flash('That slot has already passed.', 'danger')
        return redirect(url_for('bookings.detail', service_id=slot.service_id))

    user_id = session['user_id']

    # Guard: prevent duplicate booking by the same user
    already = Booking.query.filter_by(
        slot_id=slot_id, user_id=user_id, status='confirmed'
    ).first()
    if already:
        flash('You already have a booking for that slot.', 'warning')
        return redirect(url_for('bookings.my_bookings'))

    # Guard: enforce capacity — count confirmed bookings for this slot
    confirmed = _confirmed_count(slot_id)
    if confirmed >= slot.capacity:
        flash('Sorry, that slot is now fully booked.', 'danger')
        return redirect(url_for('bookings.detail', service_id=slot.service_id))

    # All checks passed — create the booking
    notes = request.form.get('notes', '').strip() or None
    booking = Booking(user_id=user_id, slot_id=slot_id, notes=notes)
    db.session.add(booking)
    db.session.commit()

    flash(f'Booking confirmed for {slot.service.name} on '
          f'{slot.date.strftime("%d %b %Y")} at {slot.start_time.strftime("%H:%M")}.', 'success')
    return redirect(url_for('bookings.confirm', booking_id=booking.id))


# ─────────────────────────────────────────────────────────────────────────────
# CONFIRMATION  —  GET /bookings/confirm/<booking_id>
# ─────────────────────────────────────────────────────────────────────────────

@bookings_bp.route('/bookings/confirm/<int:booking_id>')
@login_required
def confirm(booking_id):
    """Show a booking confirmation page."""
    booking = Booking.query.get_or_404(booking_id)
    # Users can only see their own confirmation
    if booking.user_id != session['user_id']:
        flash('Booking not found.', 'danger')
        return redirect(url_for('bookings.my_bookings'))
    return render_template('bookings/confirm.html', booking=booking)


# ─────────────────────────────────────────────────────────────────────────────
# MY BOOKINGS  —  GET /bookings/my
# ─────────────────────────────────────────────────────────────────────────────

@bookings_bp.route('/bookings/my')
@login_required
def my_bookings():
    """Show the current user's bookings, newest first."""
    bookings = (
        Booking.query
        .filter_by(user_id=session['user_id'])
        .order_by(Booking.created_at.desc())
        .all()
    )
    return render_template('bookings/my_bookings.html', bookings=bookings, today=date_type.today())


# ─────────────────────────────────────────────────────────────────────────────
# CANCEL BOOKING  —  POST /bookings/<booking_id>/cancel
# ─────────────────────────────────────────────────────────────────────────────

@bookings_bp.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
@login_required
def cancel(booking_id):
    """Cancel a booking. Only the owner can cancel their own booking."""
    booking = Booking.query.get_or_404(booking_id)

    # Ownership check — users may not cancel other people's bookings
    if booking.user_id != session['user_id']:
        flash('Booking not found.', 'danger')
        return redirect(url_for('bookings.my_bookings'))

    if booking.status == 'cancelled':
        flash('That booking is already cancelled.', 'info')
        return redirect(url_for('bookings.my_bookings'))

    # Mark cancelled rather than deleting so history is preserved
    booking.status = 'cancelled'
    db.session.commit()
    flash('Your booking has been cancelled.', 'info')
    return redirect(url_for('bookings.my_bookings'))


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — LIST SERVICES  —  GET /admin/services
# ─────────────────────────────────────────────────────────────────────────────

@bookings_bp.route('/admin/services')
@login_required
def admin_services():
    """List all bookable services (active and inactive) for admin management."""
    guard = _admin_only()
    if guard:
        return guard
    services = BookableService.query.order_by(BookableService.created_at.desc()).all()
    return render_template('admin/services.html', services=services)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — CREATE SERVICE  —  GET/POST /admin/services/new
# ─────────────────────────────────────────────────────────────────────────────

@bookings_bp.route('/admin/services/new', methods=['GET', 'POST'])
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
            return redirect(url_for('bookings.admin_services'))

    return render_template('admin/service_form.html', service=None, error=error, action='new')


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — EDIT SERVICE  —  GET/POST /admin/services/<id>/edit
# ─────────────────────────────────────────────────────────────────────────────

@bookings_bp.route('/admin/services/<int:service_id>/edit', methods=['GET', 'POST'])
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
            return redirect(url_for('bookings.admin_services'))

    return render_template('admin/service_form.html', service=service, error=error, action='edit')


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — DELETE SERVICE  —  POST /admin/services/<id>/delete
# ─────────────────────────────────────────────────────────────────────────────

@bookings_bp.route('/admin/services/<int:service_id>/delete', methods=['POST'])
@login_required
def admin_service_delete(service_id):
    """Delete a bookable service. Blocked if the service has any time slots."""
    guard = _admin_only()
    if guard:
        return guard

    service = BookableService.query.get_or_404(service_id)

    # Guard: deleting a service with slots would leave orphaned slot/booking rows
    if service.slots:
        flash(
            f'Cannot delete "{service.name}" — it has existing time slots. '
            'Delete all slots first, or deactivate the service instead.',
            'danger'
        )
        return redirect(url_for('bookings.admin_services'))

    name = service.name
    db.session.delete(service)
    db.session.commit()
    flash(f'Service "{name}" deleted.', 'info')
    return redirect(url_for('bookings.admin_services'))


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — ADD TIME SLOT  —  GET/POST /admin/services/<id>/slots/new
# ─────────────────────────────────────────────────────────────────────────────

@bookings_bp.route('/admin/services/<int:service_id>/slots/new', methods=['GET', 'POST'])
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

        # Validate all fields
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
            return redirect(url_for('bookings.admin_services'))

    return render_template('admin/slot_form.html', service=service, error=error)


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — DELETE SLOT  —  POST /admin/slots/<id>/delete
# ─────────────────────────────────────────────────────────────────────────────

@bookings_bp.route('/admin/slots/<int:slot_id>/delete', methods=['POST'])
@login_required
def admin_slot_delete(slot_id):
    """Delete a time slot. Blocked if any confirmed bookings exist for it."""
    guard = _admin_only()
    if guard:
        return guard

    slot = TimeSlot.query.get_or_404(slot_id)
    service_id = slot.service_id

    # Guard: don't allow deletion if confirmed bookings reference this slot
    confirmed = _confirmed_count(slot_id)
    if confirmed > 0:
        flash(
            f'Cannot delete that slot — it has {confirmed} confirmed booking(s). '
            'Cancel those bookings first.',
            'danger'
        )
        return redirect(url_for('bookings.admin_services'))

    db.session.delete(slot)
    db.session.commit()
    flash('Time slot deleted.', 'info')
    return redirect(url_for('bookings.admin_services'))


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN — ALL BOOKINGS  —  GET /admin/bookings
# ─────────────────────────────────────────────────────────────────────────────

@bookings_bp.route('/admin/bookings')
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
