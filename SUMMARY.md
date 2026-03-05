# Project Summary
Everything built in this project, explained in plain English. Written as a reference for documentation and exam use.

---

## What is this project?

A **full-stack web application** built with Python and Flask. It has four main parts:

1. **Auth system** — users can register, verify their email, log in (with optional 2FA), log out, and reset their password securely.
2. **Shop** — logged-in users can browse a product catalogue, add items to a cart, pay via Stripe, and receive an HTML receipt email.
3. **Booking system** — users can search available time slots for bookable services and reserve them; double-booking and capacity limits are enforced.
4. **Admin panel** — admin accounts can manage products, bookable services, time slots, and view all bookings without touching the database directly.

---

## Quick start (exam / demo)

```
pip install -r requirements.txt
# Create .env with SECRET_KEY, GMAIL_ADDRESS, GMAIL_APP_PASSWORD, STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY
python seed.py   # creates tables + admin account + demo products
python app.py
```

| Account | Email | Password |
|---------|-------|----------|
| Admin   | admin@admin.com | Admin1234 |
| Test user | user@test.com | User1234 |

---

## File structure

```
project/
├── app.py               — starts the app, wires everything together
├── models.py            — all database table definitions (User, Product, Order, OrderItem)
├── extensions.py        — shared extension objects: CSRF, rate limiter, mail sender
├── seed.py              — one-time setup script: creates tables, admin user, demo products
├── requirements.txt     — list of packages to install
├── .gitignore           — tells Git what NOT to commit (e.g. .env, database file)
├── .env                 — your secret credentials (never committed to GitHub)
│
├── auth/                — Blueprint: everything to do with authentication
│   ├── __init__.py      — creates the Blueprint object (auth_bp)
│   ├── forms.py         — WTForms form classes: LoginForm, RegistrationForm, ProfileForm, etc.
│   ├── helpers.py       — shared functions: token generation, email sending, login_required
│   └── routes.py        — route handlers: /login, /register, /logout, /verify/*, /forgot-password, etc.
│
├── main/                — Blueprint: dashboards, profile, public pages, admin product management
│   ├── __init__.py      — creates the Blueprint object (main_bp)
│   └── routes.py        — /user_dashboard, /admin_dashboard, /profile, /about, /privacy, /terms,
│                          /admin/products, /admin/products/new, /admin/products/<id>/edit|delete
│
├── shop/                — Blueprint: product catalogue, cart, checkout, orders
│   ├── __init__.py      — creates the Blueprint object (shop_bp)
│   └── routes.py        — /shop, /shop/<id>, /cart, /cart/add|remove, /checkout/*, /orders
│
├── static/              — public files served directly (CSS, images)
│   └── css/
│       ├── privacy.css  — styles for the Privacy Policy page (green scheme)
│       ├── terms.css    — styles for the Terms of Service page (red scheme)
│       └── shop.css     — styles for all shop, cart, and admin product pages
│
└── templates/           — all HTML pages, organised by blueprint
    ├── auth/
    │   ├── login.html
    │   ├── registration.html
    │   ├── forgot_password.html
    │   ├── reset_password.html
    │   ├── verify_pending.html
    │   └── resend_verification.html
    ├── main/
    │   ├── about.html
    │   ├── user_dashboard.html
    │   ├── admin_dashboard.html
    │   ├── profile.html
    │   ├── privacy.html
    │   └── terms.html
    ├── shop/
    │   ├── catalogue.html
    │   ├── product.html
    │   ├── cart.html
    │   ├── success.html
    │   ├── cancel.html
    │   └── orders.html
    └── admin/
        ├── products.html
        └── product_form.html
```

### Why Blueprints?
Each Blueprint is a self-contained feature module with its own `__init__.py` and `routes.py`. Blueprints register their routes with `app.register_blueprint()` in `app.py`. The benefit: adding a new section (e.g. `api/` or `blog/`) means creating one new folder — no existing files need to be touched. It also makes it obvious where to look for any given feature.

---

## The 8 security features

### 1. CSRF Protection
**What it is:** Cross-Site Request Forgery — a malicious website tricks your browser into submitting a form on another site without your knowledge.

**How it works in this project:**
- Flask-WTF is initialised in `extensions.py` as `csrf = CSRFProtect()` and attached to the app in `app.py` with `csrf.init_app(app)`. This enables CSRF protection **globally** — every POST form must include a valid token.
- Every WTForms form class (e.g. `LoginForm`, `RegistrationForm`) inherits from `FlaskForm`, which automatically injects a hidden `{{ form.hidden_tag() }}` field into templates. This field contains a random token signed with the app's `SECRET_KEY`.
- When a form is submitted, Flask-WTF checks the token. If it's missing or wrong, the submission is rejected.
- The CSRF error handler in `app.py` catches `CSRFError` and shows a user-friendly flash message instead of a raw error page.

### 2. Email Validation (Regex)
**What it is:** Checking that the email address entered looks like a real email.

**How it works in this project:**
- Two-layer check on registration (`auth/routes.py`):
  1. WTForms `Email()` validator (from `wtforms.validators`) — checks basic format.
  2. A custom regex in the route: `re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email)` — pattern means: one or more valid characters, then `@`, then a domain name, then `.`, then at least 2 letters.
- Email is also normalised before any check: `email.strip().lower()` — removes spaces and makes it lowercase so `User@Test.COM` and `user@test.com` are treated as the same address.

### 3. Password Hashing
**What it is:** Passwords are never stored as plain text. If the database is ever stolen, attackers can't read any password.

**How it works in this project:**
- `generate_password_hash(password)` from `werkzeug.security` is called whenever a password is saved (registration, password reset, profile password change). It produces a hash string like `pbkdf2:sha256:600000$salt$hash`.
- `check_password_hash(stored_hash, submitted_password)` is called on every login. It hashes the submitted password and compares it — the raw password is never compared directly.
- **Why PBKDF2 and not plain SHA256?** SHA256 is fast — a GPU can compute billions of hashes per second, making brute-force easy. PBKDF2 applies the hash function 600,000 times (iterations) by default, making each attempt thousands of times slower. It also includes a random **salt** per password, so two users with the same password get different hashes.

### 4. Enhanced Password Validation
**What it is:** Forcing users to pick a harder-to-guess password.

**Rules enforced (in `auth/routes.py` using `re` module):**
- Minimum 8 characters: `len(password) < 8`
- At least one number: `re.search(r"\d", password)`
- At least one uppercase letter: `re.search(r"[A-Z]", password)`

These same rules are re-applied on the password reset page and the profile password-change form.

### 5. Server-Side Form Validation
**What it is:** Even if someone bypasses browser-side checks (e.g. by using curl or Postman directly), the server still validates everything.

**What is checked server-side on registration:**
1. All required fields are present
2. Email regex matches
3. Passwords match
4. Password is 8+ characters
5. Password contains a digit
6. Password contains an uppercase letter
7. Terms checkbox is ticked (`form.agree_terms.data`)
8. Email is not already in the database (`User.query.filter_by(email=email).first()`)

Only if all checks pass does the account get created.

### 6. Rate Limiting
**What it is:** Limits how many requests a single IP address can make to a route per time window. Stops brute-force attacks and mass registration spam.

**Implemented with Flask-Limiter (`extensions.py` → `limiter = Limiter(...)`).**

| Route | Limit | Reason |
|-------|-------|--------|
| `/login` | 5 per minute | Prevents password guessing |
| `/register` | 5 per minute | Prevents mass account creation |
| `/forgot-password` | 5 per hour | Prevents reset-link spam |
| `/resend-verification` | 3 per hour | Prevents email flooding |
| `/about`, `/privacy`, `/terms` | Exempt (`@limiter.exempt`) | Public info pages, no need to restrict |

### 7. Client-Side Validation
**What it is:** JavaScript in `registration.html` checks the password before the form is submitted. Gives users instant feedback without a page reload.

**Important:** This is a convenience feature only. It can be bypassed by anyone who disables JavaScript or sends a raw request. The server-side checks in `auth/routes.py` are the real security — the client-side is just UX.

### 8. Terms & Conditions Agreement
**What it is:** Users must tick a checkbox agreeing to the Terms of Service before their account is created.

**How it works:**
- `RegistrationForm` in `auth/forms.py` has `agree_terms = BooleanField(...)`.
- The route checks `form.agree_terms.data` and returns an error if it's `False`.
- The checkbox label links to `/terms` (opens in a new tab) so users can read the full terms.

---

## How sessions work (login state)

Flask sessions are **signed cookies** stored in the user's browser. The cookie is signed with `SECRET_KEY` — this means the user can read the contents but cannot tamper with them (any modification breaks the signature and Flask rejects it).

**What gets stored in the session on login** (`auth/helpers.py` → `set_user_session()`):

```python
session.permanent = remember   # True = session survives browser close (Remember Me)
session['user_id']   = user.user_id    # Used to look up user on future requests
session['user_name'] = user.full_name  # Shown in the UI ("Welcome, John!")
session['user_role'] = user.role       # 'user' or 'admin' — controls routing
```

**Remember Me:** When the user ticks "Remember Me" on the login form, `session.permanent` is set to `True`. Flask then uses `PERMANENT_SESSION_LIFETIME` (default 31 days) as the cookie expiry, so the session survives after the browser is closed.

**Logout** (`/logout`): calls `session.clear()` — wipes everything from the session, making the user anonymous again.

**Checking login:** Routes use `'user_id' in session` to determine if the user is logged in.

---

## How `@login_required` works

`login_required` is a custom decorator defined in `auth/helpers.py`:

```python
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated
```

When placed above a route (`@login_required`), it runs first and checks for `user_id` in the session. If missing, the user is redirected to `/login` before the route function even runs. `@wraps(f)` preserves the original function's name (important for Flask's URL routing).

---

## How admin-only routes work

Admin routes use two layers of protection:

1. `@login_required` — ensures the user is logged in.
2. `_admin_only()` helper — checks `session.get('user_role') != 'admin'`. If the user is logged in but not an admin, they are redirected to the user dashboard with an error flash.

```python
@main_bp.route('/admin/products')
@login_required
def admin_products():
    guard = _admin_only()
    if guard:
        return guard
    ...
```

This means a regular user who tries to visit `/admin/products` is blocked at the `_admin_only()` check, even though they are logged in.

---

## How tokens work (email verification & password reset)

Tokens are created by `itsdangerous.URLSafeTimedSerializer` (`auth/helpers.py`).

**Generating a token:**
```python
s = URLSafeTimedSerializer(current_app.secret_key)
token = s.dumps(user_email, salt='email-verify')
```
The email address is serialised and **signed** (not encrypted — the content is readable) using HMAC with the `SECRET_KEY`. The `salt` makes tokens for different purposes incompatible: a token created with `salt='email-verify'` cannot be used at the `/reset-password` route (which expects `salt='password-reset'`), even though both are signed with the same key.

**Verifying a token:**
```python
email = s.loads(token, salt='email-verify', max_age=3600)
```
`max_age=3600` means the token expires after 1 hour. If tampered with, `BadSignature` is raised. If expired, `SignatureExpired` is raised. Both are caught in the routes and shown as user-friendly error messages.

**Anti-enumeration:** Both `/forgot-password` and `/resend-verification` always show the **same vague response** regardless of whether the email exists in the database. This prevents attackers from probing which emails are registered.

---

## Authentication flow

### Registration
1. User fills in `/register`
2. Client-side JS checks password strength
3. POST → server runs the full validation chain (8 checks)
4. If valid: `User` row created with `is_verified=False`, password stored as hash
5. `send_verification_email()` builds a token URL and sends it via Gmail SMTP
6. User redirected to "Check your inbox" page (`/verify-pending`)

### Email verification
1. User clicks the link: `/verify/<token>`
2. `verify_token(token, salt='email-verify')` decodes the token → email address
3. `User.query.filter_by(email=email).first()` finds the account
4. `user.is_verified = True` → saved to DB
5. User redirected to `/login`

### Login
1. POST to `/login` with email + password
2. `email.strip().lower()` normalises the input
3. `User.query.filter_by(email=email).first()` looks up the account
4. `check_password_hash(user.password_hash, password)` verifies the password
5. `user.is_verified` is checked — unverified accounts are blocked with a message pointing to `/resend-verification`
6. On success: `set_user_session(user, remember=form.remember_me.data)` writes session data
7. `redirect_to_dashboard(user.role)` sends admin → `/admin_dashboard`, others → `/user_dashboard`

### Forgot password
1. User submits email at `/forgot-password`
2. Server always shows the same message (anti-enumeration)
3. If user exists: `send_password_reset_email()` sends a token link (different salt, same 1-hour expiry)
4. User clicks `/reset-password/<token>` → same strength checks as registration
5. `user.password_hash = generate_password_hash(new_password)` + `user.is_verified = True` saved

### Profile update (`/profile`)
- User can update their full name at any time.
- Password change is **optional**: only processed if `new_password` field is filled in.
- Requires correct current password before allowing a change (`check_password_hash`).
- Same strength rules applied to the new password.
- Session `user_name` is updated immediately so the greeting in the UI reflects the new name.

---

## How the shop works

### Cart design
The cart lives in the Flask session as a plain dictionary:
```python
session['cart'] = {'1': 2, '3': 1}  # product_id (as string): quantity
```
- String keys because session data is serialised to JSON, which only allows string keys.
- `session.modified = True` must be set after mutating a dict in the session, so Flask knows to re-sign and re-save the cookie.
- The cart clears when the user logs out (`session.clear()`) or the session expires.

### Customer flow
1. `/shop` — queries `Product.query.filter_by(is_active=True)` — only shows live products
2. Click "Add to Cart" → POST `/cart/add/<id>` — increments `session['cart'][str(id)]`
3. `/cart` — loads each product from DB, calculates line totals and subtotal
4. "Checkout" → POST `/checkout/create` — builds Stripe `line_items` from the cart and calls `stripe.checkout.Session.create()`
5. Stripe redirects user to its hosted payment page
6. After payment: Stripe redirects to `/checkout/success?session_id=...`
7. Server calls `stripe.checkout.Session.retrieve(session_id)` to **verify** the payment status with Stripe directly
8. Idempotency check: `Order.query.filter_by(stripe_checkout_session_id=session_id).first()` — if this session has already been processed, the existing order is shown instead of creating a duplicate
9. New `Order` row (status `'paid'`) + `OrderItem` rows saved to DB; cart cleared from session

### Price in pence
All prices are stored as integers in pence (£9.99 → `999`) to avoid floating-point rounding errors. The admin enters pounds (e.g. `9.99`), the route converts it: `int(round(float(price_str) * 100))`.

---

## How admin product management works

**Access:** `/admin/products` — protected by `@login_required` + `_admin_only()`.

| Action | Route | What happens in the DB |
|--------|-------|------------------------|
| View all products | GET `/admin/products` | `SELECT * FROM products ORDER BY created_at DESC` |
| Add a product | GET/POST `/admin/products/new` | `INSERT` into `products` |
| Edit a product | GET/POST `/admin/products/<id>/edit` | `UPDATE` the `products` row |
| Delete a product | POST `/admin/products/<id>/delete` | `DELETE` the row |

**Delete uses POST (not GET)** — this prevents accidental deletion by simply visiting a URL (e.g. a prefetch or link click).

**image_url** is optional — the field is `nullable=True` in the model. If the admin leaves it blank, the form stores `None` (via `request.form.get('image_url', '').strip() or None`). Templates show a default icon when `image_url` is `None`.

**Deactivating vs deleting:**
- Unchecking "Active" sets `is_active=False`. The product disappears from `/shop` (which filters `WHERE is_active=True`) but the DB row is kept. Past `order_items` still reference it correctly.
- Deleting removes the row entirely. Only safe for products that have **never been ordered**. If `order_items` rows reference the product, the `/orders` page will error trying to join to a missing row.

**Price changes:** Editing a product's price only affects future purchases. Past `order_items` rows store a `unit_price` snapshot (the price at time of purchase), so historical order totals are always accurate.

---

## The database

**Type:** SQLite — a single file (`app.db`) in the project folder. No separate server needed. Created automatically by `db.create_all()` when the app starts.

**ORM:** SQLAlchemy — maps Python classes to database tables. `db.session.add()`, `db.session.commit()`, `db.session.delete()` replace writing raw SQL.

### `users` table

| Column | Type | Notes |
|--------|------|-------|
| `user_id` | Integer PK | Auto-incremented |
| `full_name` | String(120) | First + last stored together |
| `email` | String(120) unique | Lowercased before storage |
| `password_hash` | String(256) | PBKDF2-SHA256 hash — never the real password |
| `role` | String(20) | `'user'` (default) or `'admin'` |
| `join_date` | DateTime | Auto-set to `datetime.utcnow` on creation |
| `is_verified` | Boolean | `False` until verification email clicked |

### `products` table

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Auto-incremented |
| `name` | String(120) | Shown in shop |
| `description` | Text | Full description |
| `price` | Integer | In pence — e.g. `999` = £9.99 |
| `image_url` | String(300) nullable | Optional; `None` → default icon |
| `is_active` | Boolean | `True` = visible in shop |
| `created_at` | DateTime | Auto-set on creation |

### `orders` table

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Auto-incremented |
| `user_id` | Integer FK → `users.user_id` | Who placed the order |
| `stripe_checkout_session_id` | String(200) unique | Used for idempotency check + Stripe lookup |
| `amount_total` | Integer | Total paid in pence |
| `status` | String(20) | `'pending'` → `'paid'` or `'failed'` |
| `created_at` | DateTime | Auto-set on creation |

### `order_items` table

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | Auto-incremented |
| `order_id` | Integer FK → `orders.id` | Which order this belongs to |
| `product_id` | Integer FK → `products.id` | Which product |
| `quantity` | Integer | How many bought |
| `unit_price` | Integer | **Price snapshot at time of purchase** — independent of current product price |

---

## Stripe integration

### How payment verification works
1. The server creates a Stripe Checkout Session (server-side with `stripe.api_key = secret_key`).
2. The user is redirected to Stripe's hosted page (Stripe handles card data — our server never sees card numbers).
3. After payment, Stripe redirects to `/checkout/success?session_id=cs_...`.
4. The server calls `stripe.checkout.Session.retrieve(session_id)` to ask Stripe directly: was this actually paid?
5. Only if `checkout_session.payment_status == 'paid'` does the server write the order to the DB.

### Idempotency
Before writing an order, the route checks:
```python
existing = Order.query.filter_by(stripe_checkout_session_id=session_id).first()
```
If an order with that session ID already exists (e.g. user refreshed the success page), the existing order is returned instead of creating a duplicate.

### Test card
```
Card number:  4242 4242 4242 4242
Expiry:       Any future date (e.g. 12/29)
CVC:          Any 3 digits (e.g. 123)
```
Other test cards:
- `4000 0025 0000 3155` — triggers 3D Secure
- `4000 0000 0000 9995` — always declines

### Currency
Hardcoded to GBP. To change, find `'currency': 'gbp'` in `shop/routes.py` and replace with any ISO 4217 code (e.g. `'usd'`, `'eur'`).

---

## Key technologies

| Package | What it does |
|---------|-------------|
| Flask | Web framework — handles routing, templates, sessions |
| Flask-WTF | Adds CSRF protection; integrates WTForms with Flask |
| WTForms | Defines and validates form fields |
| Flask-SQLAlchemy | Connects Flask to a database using Python objects (ORM) |
| Flask-Limiter | Rate limits routes by IP address |
| Flask-Mail | Sends emails via Gmail SMTP |
| Werkzeug | Provides `generate_password_hash` / `check_password_hash` (comes with Flask) |
| itsdangerous | Creates signed, time-limited tokens for email links (`URLSafeTimedSerializer`) |
| python-dotenv | Loads `.env` file into `os.environ` at startup |
| stripe | Creates payment sessions and verifies payments via the Stripe API |
| re (stdlib) | Python's built-in regex module — used for email and password validation |
| secrets (stdlib) | `secrets.randbelow()` — cryptographically secure OTP generation for 2FA |

---

## How the booking system works

### Overview
The booking system is a **generic, reusable template** — admin creates named services (e.g. "Consultation", "Studio Session"), attaches time slots with date/time/capacity, and users browse and reserve them. No payment is required.

### Models
Three new tables added to `models.py`:

| Model | Table | Purpose |
|-------|-------|---------|
| `BookableService` | `bookable_services` | A named service admin creates (name, description, active flag) |
| `TimeSlot` | `time_slots` | A specific date + start/end time + capacity attached to a service |
| `Booking` | `bookings` | A user's reservation for a slot (status: `confirmed` / `cancelled`) |

### User flow
1. `/bookings` — search/browse active services; optional date filter shows only services with available slots on that day
2. `/bookings/<service_id>` — see all upcoming slots for a service, colour-coded: green (available), blue (already booked by you), grey (full)
3. Book form on each available slot → POST `/bookings/<slot_id>/book`
4. `/bookings/confirm/<id>` — confirmation page with booking reference
5. `/bookings/my` — list of all the user's bookings with cancel button

### Admin flow
1. `/admin/services` — list all services; each shows its time slots with confirmed/capacity counts
2. `/admin/services/new` — create a service (name, description, active toggle)
3. `/admin/services/<id>/edit` — edit a service
4. `/admin/services/<id>/slots/new` — add a time slot (date, start time, end time, capacity)
5. `/admin/bookings` — read-only view of every booking across all services

### Double-booking / capacity enforcement
Two guards run in sequence in `POST /bookings/<slot_id>/book`:

```python
# Guard 1: prevent the same user booking the same slot twice
already = Booking.query.filter_by(slot_id=slot_id, user_id=user_id, status='confirmed').first()

# Guard 2: enforce capacity ceiling
confirmed_count = Booking.query.filter_by(slot_id=slot_id, status='confirmed').count()
if confirmed_count >= slot.capacity:
    flash('Sorry, that slot is now fully booked.', 'danger')
```

`capacity=1` (the default) means only one user can ever hold a confirmed booking — classic no-double-booking. Set `capacity=10` to allow 10 concurrent bookings on the same slot.

### Cancellation
Bookings are never hard-deleted. Setting `status='cancelled'` preserves history and frees up the space in the capacity count (only `status='confirmed'` bookings count against capacity).

### Admin delete guards
- **Delete service** — blocked if the service has any time slots; admin must delete all slots first (or deactivate instead).
- **Delete slot** — blocked if any confirmed bookings reference it; admin must cancel those bookings first.

### DB note
Three new tables. **Delete `app.db` and re-run `python seed.py`** after pulling this change — `db.create_all()` does not add new tables to an existing database.
