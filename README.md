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
- CSRF Protection
- Email Validation (Email Regex)
- Password Hashing
- Enhanced Password Validation
- Server-Side Form Validation
- Rate Limiting
- Client-Size Validation
- Logout route
- Email Verification
- Forgot Password / Recovery
- Terms of Serivce
- Privacy Policy 
- Secure Session Management
- Role-Based Access Contro
- Remember Me 
- Resend Verification Email
- User Profile Management
- Input Sanitisation
