# Brew & Bite

Brew & Bite is a vegetarian cafe ordering application built with Python, Flask,
Flask-SQLAlchemy, and Flask-Login, with an HTML/CSS/JavaScript frontend.

Customers browse the menu, add items to a cart, place orders, and view order
history. Admins manage the menu and orders through a dedicated admin panel at
`/admin`.

---

## 1. What you need

- **Python 3.9+** (Flask 3.x requires Python 3.8+)
- `pip` (comes with Python)
- Git (to clone the repo)

---

## 2. Clone and install

```bash
# Clone the repository
git clone https://github.com/vishalk-20/Brew-and-Bite.git
cd Brew-and-Bite

# Create a virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Dependencies (`requirements.txt`):

- Flask>=3.0,<4
- Flask-SQLAlchemy>=3.0,<4
- Flask-Login>=0.6,<1
- Werkzeug>=3.0,<4
- gunicorn>=21.0,<22 (production WSGI server)

---

## 3. Configure environment variables

Create a `.env` file in the project root (never commit real secrets):

```bash
# Windows (PowerShell):
# copy .env.example .env   # if .env.example exists, otherwise create manually
# then edit .env with Notepad or your editor

# macOS / Linux:
touch .env
```

Add the variables you need:

| Variable | Purpose | Default | Notes |
|----------|---------|---------|-------|
| `APP_ENV` | `development` or `production` | `development` | Controls debug default and cookie security. |
| `SECRET_KEY` | Session signing key | random (dev only) | **Required in production.** Generate with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `FLASK_DEBUG` | Dev-server debug on/off | `true` (dev) | Ignored in production. |
| `SESSION_COOKIE_SECURE` | HTTPS-only session cookies | `false` dev / `true` prod | Set `true` behind HTTPS. |
| `DELIVERY_FEE` | Delivery fee in rupees | `40.00` | Applied to every order. |
| `HOST` | Dev-server bind address | `127.0.0.1` | Only used by `python app.py`. |
| `PORT` | Dev-server port | `5000` | Only used by `python app.py`. |

Example `.env` for local development:

```env
APP_ENV=development
SECRET_KEY=dev-secret-change-me
FLASK_DEBUG=true
DELIVERY_FEE=40.00
HOST=127.0.0.1
PORT=5000
```

---

## 4. Initialize the database

The SQLite database is created automatically on first startup at
`instance/cafe.db` (gitignored). `db.create_all()` runs on startup, plus safe
auto-migrations that add missing columns (`users.phone`, `cart_items.notes`)
only when needed.

No manual migration step is required.

---

## 5. Create an admin user (required)

Admin routes do not work until an admin user exists. Run:

```bash
flask create-admin
```

You are prompted interactively for **email**, **password**, and **name**. This
creates a user with `role="admin"`.

> Customers register themselves through the customer registration page
> (`/register`) — admin accounts are created only via this command.

---

## 6. Run the development server

```bash
python app.py
```

The app serves on `http://127.0.0.1:5000` with debug mode on by default.

- Customer login: `/login`
- Customer registration: `/register`
- Admin login: `/admin/login` (dedicated admin page)
- Admin dashboard: `/admin/` (after logging in as admin)

---

## 7. Run the tests

There is no pytest suite. Each `test_*.py` file is a manual runner that prints
pass/fail:

```bash
python test_auth.py
python test_cart.py
python test_orders.py
python test_admin_orders.py
python test_customer_dashboard.py
python test_production_config.py
```

Each file defines `test_*` functions plus a `__main__` block that runs them all.

---

## 8. Run in production

Do **not** run `python app.py` (the debug dev server) in production. Use
gunicorn behind a reverse proxy (nginx, Caddy, Cloudflare Tunnel, etc.) that
terminates TLS:

```bash
# From the project root, with APP_ENV=production and SECRET_KEY set:
gunicorn app:app
```

Set these for production:

```env
APP_ENV=production
SECRET_KEY=<generate with python -c "import secrets; print(secrets.token_hex(32))">
SESSION_COOKIE_SECURE=true
FLASK_DEBUG=false
```

Operational notes:

- Database: SQLite at `instance/cafe.db` — single-instance, not suitable for
  multi-replica deployment. Back it up regularly.
- Uploaded product images live in `app/static/uploads/` (gitignored) — mount a
  persistent volume so images survive redeploys.
- Never commit `SECRET_KEY`, `.env`, `instance/`, or `venv/` to source control.

---

## 9. Project structure

```
Brew-and-Bite/
├── app.py                      # Entry point; creates app via create_app() factory
├── requirements.txt            # Python dependencies
├── DEPLOYMENT.md               # Detailed deployment & operations guide
├── README.md                   # This file
├── test_auth.py                # Manual test runner (auth)
├── test_cart.py                # Manual test runner (cart)
├── test_orders.py              # Manual test runner (orders)
├── test_admin_orders.py        # Manual test runner (admin orders)
├── test_customer_dashboard.py  # Manual test runner (customer dashboard)
├── test_production_config.py   # Manual test runner (production config)
├── instance/                   # SQLite database (gitignored)
│   └── cafe.db
├── app/
│   ├── __init__.py             # create_app() factory, blueprint registration
│   ├── extensions.py           # db, login_manager
│   ├── models.py               # User, Category, Product, Cart, CartItem, Order, OrderItem
│   ├── scripts/
│   │   └── seed_menu_items.py  # Menu seed script
│   ├── admin/                  # Admin blueprint (routes + templates)
│   ├── auth/                   # Auth blueprint (login, register, logout)
│   ├── cart/                   # Cart blueprint
│   ├── customer/               # Customer blueprint
│   ├── main/                   # Customer-facing routes (home, menu)
│   ├── orders/                 # Orders blueprint (checkout, confirmation)
│   ├── static/
│   │   └── css/style.css       # All styling + design tokens
│   └── templates/              # Jinja2 templates (base, admin, auth, cart, etc.)
├── docs/
│   └── superpowers/specs/      # Feature design documents
└── venv/                       # Virtual environment (gitignored)
```

---

## 10. License

Add your license here if you have one (e.g., MIT, Apache-2.0). If you don't
want one, you can remove this section — by default, all rights are reserved.
