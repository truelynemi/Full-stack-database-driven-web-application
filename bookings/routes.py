# bookings/routes.py
# ─────────────────────────────────────────────────────────────────────────────
# User-facing booking routes.
#
#   GET  /bookings                      — search / browse services
#   GET  /bookings/<service_id>         — service detail + slot list
#   POST /bookings/<slot_id>/book       — create a booking
#   GET  /bookings/confirm/<booking_id> — booking confirmation
#   GET  /bookings/my                   — user's own bookings
#   POST /bookings/<booking_id>/cancel  — cancel a booking
# ─────────────────────────────────────────────────────────────────────────────

from datetime import date as date_type, datetime

from flask import render_template, redirect, url_for, flash, session, request

from models import db, BookableService, TimeSlot, Booking
from auth.helpers import login_required
from bookings import bookings_bp


# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────

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
