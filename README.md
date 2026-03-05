# Full-stack database-driven web application
I will use this repository to create a full-stack development with Flask, SQLite, HTML and more. <br>
**(Developed with assistance from Claude AI)**

This is not a finished project — it’s a template for my exam. Feel free to explore, learn from it, and build upon it for your own projects.

## Quick start (exam / demo)
```
pip install -r requirements.txt
# create .env with SECRET_KEY, GMAIL_*, STRIPE_* values
python seed.py   # creates tables + admin account + 4 demo products
python app.py
```
Admin login: `admin@admin.com` / `Admin1234`
Test user login: `user@test.com` / `User1234`

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
- 2FA Enable / Disable (from profile page)
- Account Deletion (danger zone, password confirmed)
- Cookie Consent Banner
- UserWay Accessibility Widget

### Shop
- Product Catalogue
- Product Detail Pages
- Shopping Cart (session-based)
- Stripe Checkout (hosted payment page)
- Order History
- HTML Order Receipt Email (sent after payment)

### Admin Panel
- Product Management (create, edit, deactivate, delete)
- Admin Dashboard

### UI / UX
- Toast Flash Messages (fixed overlay, auto-dismiss)
- Responsive base layouts (shop + admin)
- Terms of Service page
- Privacy Policy page
