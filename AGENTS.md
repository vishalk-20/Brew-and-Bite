# AGENTS.md

Guidance for AI coding agents working in this repository.

## Commands

- Dev server: `python app.py` → Flask on http://127.0.0.1:5000 (debug mode on).
- Create admin user: `flask create-admin` (interactive: email, password, name). Required before any admin route works.
- Run tests: `python test_auth.py`, `python test_cart.py`, `python test_orders.py`, `python test_admin_orders.py` — manual runners, **not** pytest. Each file defines `test_*` functions plus a `__main__` list that runs them and prints pass/fail.

## Architecture

- Entry: root `app.py` → `app.create_app()` factory in `app/__init__.py`.
- Blueprints live in `app/<name>/routes.py` and are registered in the factory; templates live in `app/templates/<name>/`.
- Models in `app/models.py`: User, Category, Product, Cart, CartItem, Order, OrderItem.
- Database: SQLite at `instance/cafe.db`. `instance/` is gitignored, so the DB is not committed; `db.create_all()` runs on startup and raw `ALTER TABLE` auto-migrations patch missing columns (`users.phone`, `cart_items.notes`) — do not duplicate them.
- Orders blueprint has no `url_prefix` → customer order routes sit at `/checkout` and `/orders/<order_number>/confirmation`.
- Admin blueprint is mounted at `/admin`; admin order routes (Feature 6) are `/admin/orders`, `/admin/orders/<order_number>`, `/admin/orders/<order_number>/status` (POST), `/admin/orders/<order_number>/payment` (POST).
- Design docs live in `docs/superpowers/specs/` (e.g. `2026-11-03-admin-order-management-design.md`).

## Conventions and gotchas

- CSRF is session-based: store `_csrf_token` in the Flask session, expose via a hidden input named `csrf_token`, validate with each blueprint's `_csrf_valid()` helper. Every POST form and test helper must send it.
- Prices are `Numeric(10,2)` Decimals; template currency format is `&#8377;{{ "%.2f"|format(price) }}` — keep this exact pattern (₹ sign, two decimals).
- Order placement: validate delivery form → create Order + OrderItems in one DB transaction → clear cart items only after commit → redirect to confirmation. Delivery fee read from `current_app.config["DELIVERY_FEE"]` (default `40.00`).
- New orders start with `order_status="pending"`, `payment_status="pending"`, `payment_method="cod"`.
- Order status transitions are enforced server-side on the `Order` model via `ALLOWED_TRANSITIONS`, `can_transition_to()`, `transition_to()`: forward-only chain `pending → confirmed → preparing → ready for pickup → out for delivery → delivered`, cancellation allowed from any non-final state; `delivered` and `cancelled` are final. Invalid transitions raise `ValueError`.
- COD payment status is updated separately via `POST /admin/orders/<order_number>/payment`; only COD orders may be marked `paid`, and duplicate "already paid" updates are rejected.
- Cart: one cart per user (unique `user_id`); unique constraint on `(cart_id, product_id)`; item notes flow into order item `special_instructions`.
- Flash categories used: `success`, `error`, `warning`, `info`.

## Design system

- `app/static/css/style.css` holds tokens and all styling. House style: flat square-cornered buttons, no gradients/shadows at rest, no eyebrows, sentence case, no index numbers.
- Order status badge classes: `badge-status-pending`, `badge-status-confirmed`, `badge-status-preparing`, `badge-status-ready-for-pickup`, `badge-status-out-for-delivery`, `badge-status-delivered`, `badge-status-cancelled`. Payment badges: `badge-paid`, `badge-pending`.

## Testing quirks

- No pytest suite: each `test_<feature>.py` is a manual runner with a `tests` list and `__main__` block.
- Each run uses `TS = str(int(time.time()))` for unique emails; tests use the real SQLite DB via the app factory.
