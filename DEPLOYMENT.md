# Brew & Bite — Deployment & Operations

Brew & Bite is a vegetarian cafe ordering application (Python, Flask,
Flask-SQLAlchemy, Flask-Login) with HTML/CSS/JavaScript frontend. This
document covers local setup, testing, production startup, and operations.
No new product features are included; this is the final polish and
deployment-readiness pass.

## 1. Required Python version and dependencies

- Python 3.9+ (Flask 3.x requires Python 3.8+).
- Dependencies are pinned in `requirements.txt`:
  - `Flask>=3.0,<4`
  - `Flask-SQLAlchemy>=3.0,<4`
  - `Flask-Login>=0.6,<1`
  - `Werkzeug>=3.0,<4`
  - `gunicorn>=21.0,<22` — production WSGI server.

Install:

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

## 2. Environment variables and configuration

Copy `.env.example` to `.env` and adjust for your environment. Never commit
real secrets.

| Variable | Purpose | Default | Notes |
|----------|---------|---------|-------|
| `APP_ENV` | `development` or `production` | `development` | Controls secure cookies, debug default, and the SECRET_KEY fail-fast check. |
| `SECRET_KEY` | Session signing key | random (dev only) | **Required in production.** Generate with `python -c "import secrets; print(secrets.token_hex(32))"`. Missing in production => app refuses to start. |
| `FLASK_DEBUG` | Dev-server debug | `true` (dev) | Honored only when not in production; production runs under gunicorn. |
| `SESSION_COOKIE_SECURE` | HTTPS-only session cookies | `false` dev / `true` prod | Set `true` when served over HTTPS behind a reverse proxy. |
| `DELIVERY_FEE` | Delivery fee in rupees | `40.00` | Applied to every order. |
| `HOST`, `PORT` | Dev server bind address | `127.0.0.1`, `5000` | Only used by `python app.py`; production uses gunicorn. |

## 3. Local setup and test commands

Database initialization happens automatically on startup (`db.create_all()` plus
auto-migrations for `users.phone` and `cart_items.notes`). The SQLite database
lives at `instance/cafe.db` (gitignored).

1. Create an admin user (required before any admin route works):

   ```bash
   flask create-admin
   ```

   You are prompted interactively for email, password, and name.

2. Start the dev server:

   ```bash
   python app.py
   ```

   Serves on `http://127.0.0.1:5000` with debug on by default.

3. Run the test suite (manual runners, not pytest). Each prints pass/fail:

   ```bash
   python test_auth.py
   python test_cart.py
   python test_orders.py
   python test_admin_orders.py
   python test_customer_dashboard.py
   python test_production_config.py
   ```

## 4. Production start command

Use gunicorn as the WSGI entry point. The application object is `app` in
`app.py` (created via the `create_app()` factory).

```bash
# From the project root, with APP_ENV=production and SECRET_KEY set:
gunicorn app:app
```

Run gunicorn behind a reverse proxy (nginx, Caddy, Cloudflare Tunnel, etc.)
that terminates TLS and forwards to `127.0.0.1:8000` (gunicorn default) or
your chosen bind. Do **not** run `python app.py` (the debug dev server) in
production.

Provider-specific steps that remain for the operator:
- Domain name and DNS.
- TLS certificate and HTTPS termination at the reverse proxy.
- Process management / supervisor (systemd, supervisor, Docker, etc.).
- Persistent storage for the database and uploaded media (see section 5).
- Backups and monitoring.

## 5. Database and persistent-file handling

- Database: SQLite at `instance/cafe.db`. Initialized on startup with
  `db.create_all()` plus safe auto-migrations that add `users.phone` and
  `cart_items.notes` only when missing. **No schema changes and no migration
  framework are introduced in Feature 8.** Do not delete, reset, or replace
  existing data.
- Uploaded product images are stored in `app/static/uploads` (gitignored).
- Both `instance/` and `app/static/uploads/` must live on **persistent storage**
  (a volume mount) in production so uploads and the database survive redeploys.
- Back up `instance/cafe.db` and `app/static/uploads/` on a regular schedule.

SQLite is single-instance and is not suitable for horizontally scaled or
multi-replica deployment; consider PostgreSQL for that.

## 6. HTTPS, secret management, backups, and operational limitations

- Terminate TLS at the reverse proxy and set `SESSION_COOKIE_SECURE=true` so
  session cookies are only sent over HTTPS.
- `SECRET_KEY` is required in production and must never be committed to source
  control. Rotate it only with the understanding that all existing sessions
  will be invalidated.
- Back up `instance/cafe.db` (the order/cart database) and `app/static/uploads/`
  (product images) regularly.
- Operational limitations (documented, not resolved in Feature 8):
  - Single-instance SQLite; not for multi-replica deployment.
  - Uploads stored on the local filesystem; ephemeral filesystems lose images
    on redeploy unless a persistent volume is mounted.
  - No MIME-type or virus scanning of uploaded images.
  - Debug stack traces are still exposed if `FLASK_DEBUG=true` is accidentally
    set in production; operators must keep debug off.
  - Custom error pages (404/500) do not catch errors raised before Flask is
    fully initialized (e.g., import errors).
