# Full-stack database-driven web application
I will use this repository to create a full-stack development with Flask, SQLite, HTML and more. <br>
**(Developed with assistance from Claude AI)**

This is not a finished project — it's a template for my exam. Feel free to explore, learn from it, and build upon it for your own projects.

## Quick start (exam / demo)
```
pip install -r requirements.txt
# create .env with SECRET_KEY, GMAIL_*, STRIPE_* values
python seed.py   # creates tables + admin and test user accounts
python app.py
```
Admin login: `admin@admin.com` / `Admin1234`
Test user login: `user@test.com` / `User1234`

> **Note:** No demo products are seeded. Add products through the admin panel after logging in as admin.

---

## Features Implemented

### Security
- CSRF Protection
- Email Validation (Email Regex)
- Password Hashing (PBKDF2-SHA256)
- Enhanced Password Validation
- Server-Side Form Validation
- Client-Side Validation
- Rate Limiting
- Input Sanitisation
- Email OTP Two-Factor Authentication (2FA)

### Authentication
- User Registration
- Email Verification
- Resend Verification Email
- Login / Logout
- Forgot Password / Recovery
- Remember Me (30-day session)
- Secure Session Management
- Role-Based Access Control (user / admin)

### User Features
- User Profile Management (name + password change)
- User email displayed on profile page
- 2FA Enable / Disable (from profile page)
- Account Deletion (danger zone, password confirmed)
- Cookie Consent Banner (on all pages)
- UserWay Accessibility Widget (on all pages)

### Shop
- Product Catalogue (admin-managed, empty until admin adds products)
- Product Detail Pages
- Shopping Cart (session-based)
- Stripe Checkout (hosted payment page)
- Order History
- HTML Order Receipt Email (sent after payment)

### Booking System
- Browse bookable services with optional date filter
- Time slot detail view with live availability
- Reserve a slot (with double-booking and capacity enforcement)
- Booking confirmation page
- My Bookings page with cancel option

### Admin Panel
- Admin Dashboard with quick-access cards
- Product Management (create, edit, deactivate, delete)
- Service Management (create, edit, delete)
- Time Slot Management (add, delete)
- All Bookings view (read-only)

### UI / UX
- Toast Flash Messages (fixed overlay, auto-dismiss, on all pages)
- Four shared base layouts: `base_auth`, `base_main`, `base_shop`, `base_admin`
- Consistent navigation and styling across the full app
- Terms of Service page
- Privacy Policy page
