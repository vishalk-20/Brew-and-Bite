# Customer Dashboard — Design Doc

Date: 2026-11-03
Topic: Feature 7 — Customer Dashboard

## Intent and the why

Brew & Bite lets customers place vegetarian orders captured as `Order` + `OrderItem` records. After checkout, a customer sees a confirmation page once, but has no dedicated place to revisit their own account or order history. Feature 7 gives logged-in customers a personal account area: a dashboard with their profile and order summary counts, a full order history, and a customer-facing order detail page. This lets customers track their own orders without contacting the cafe, and it must never expose another customer's account or orders.

## Goals

- Logged-in customers can view their own account dashboard at `/account` (welcome heading, name/email/phone profile, order summary cards, recent orders newest first).
- Customers can view their full order history at `/account/orders`, newest first, paginated.
- Customers can view a single order's details at `/account/orders/<order_number>`: historical item names/quantities/prices, subtotal, delivery fee, total, payment method/status, delivery address, current status.
- All customer-scoped queries filter by `current_user.id` on the server; no user ID is ever accepted from the URL or form to decide which orders to show.
- Unauthenticated users are redirected to login with a safe `next` destination; admins are redirected to the admin dashboard.
- Customers cannot view another customer's order by changing the order number — it returns the project's normal 404.
- No admin-only status or payment controls on customer pages; customers cannot change order status or mark payments as paid.
- Existing test suites keep passing; no checkout/payment/email/SMS changes; no database schema changes.

## Non-goals

- Online payment processing (orders remain Cash on Delivery only).
- Order status or payment changes by the customer.
- Editing the customer profile (view-only only).
- Email, SMS, or push notifications on order events.
- Adding new database tables or altering existing columns.

## Anti-goals (failure even if it technically works)

- A logged-in customer can reach another customer's order by guessing or changing the order number in the URL.
- An unauthenticated user can reach `/account`, `/account/orders`, or `/account/orders/<n>` without being redirected to login.
- An admin can view customer account data through the customer routes.
- Customer pages expose admin-only status-transition or "mark as paid" controls.
- Historical product names/prices on an order item are replaced by current product data.

## Acceptance criteria

- `GET /account`, `GET /account/orders`, and `GET /account/orders/<number>` require login; logged-out users are redirected to login with a safe `next`.
- Dashboard shows total orders, pending/in-progress orders, and completed orders counts, plus up to 5 recent orders newest first.
- `GET /account/orders` lists all of the customer's orders newest first, paginated.
- `GET /account/orders/<number>` returns 404 for an unknown order number or an order belonging to another customer.
- Order detail shows historical item/price snapshots and correct totals (subtotal, delivery fee, total).
- No admin action forms or links appear on customer pages.
- Existing `test_auth.py`, `test_cart.py`, `test_orders.py`, and `test_admin_orders.py` still pass.

## Constraints

- Reuse existing `User`, `Order`, `OrderItem` models; no new tables, no column changes.
- Reuse Flask-Login (`current_user`, `@login_required`), session-based CSRF (`csrf_token` input, `_csrf_valid()` per blueprint), flash categories (`success`/`error`/`warning`/`info`).
- New routes in a dedicated `customer` blueprint (`app/customer/routes.py`), registered in `app/__init__.py` without a `url_prefix` (matching `orders_bp`).
- Prices formatted as `&#8377;{{ "%.2f"|format(price) }}` (₹, two decimals).
- Order status badges reuse existing `.badge-status-*` classes; payment badges reuse `.badge-paid`/`.badge-pending`.
- Templates extend `base.html`; the nav "My Account" link is retargeted to the dashboard.
- Delivery fee is already stored on `Order` (`delivery_fee`, included in `total_amount`); no config read needed for read-only display.
- No online payments, no email/SMS.

## Approaches considered

1. **New dedicated `customer` blueprint** (chosen).
   - `app/customer/routes.py` with `customer_bp`, no `url_prefix`.
   - Routes `/account`, `/account/orders`, `/account/orders/<order_number>`.
   - `customer_required` guard (login + non-admin) modeled on orders' `customer_required`.
   - Keeps customer account concerns separate from `main` (home/menu) and `orders` (checkout/confirmation).
   - Matches the project's blueprint-per-area pattern (auth, admin, main, cart, orders).

2. **Add routes to existing `main_bp`** (rejected).
   - Simpler: no new file, no `__init__.py` change.
   - Mixes customer account concerns with general site routes; less modular as the account area grows.

3. **Enhance existing `/customer` (`main.customer_home`) as the dashboard** (rejected).
   - Task explicitly asks for `/account` or `/dashboard`; reusing `/customer` doesn't match the requested path.
   - `/customer` currently shows featured menu items; mixing in order history dilutes its purpose.

## How it gets built (decisions made)

**Routes** (in `app/customer/routes.py`):

- `GET /account` → `customer.dashboard`
  - Requires `customer_required` guard.
  - Welcome heading using the logged-in customer's name.
  - Profile section: name, email, phone (existing `User` fields only; no new fields).
  - Order summary cards: total orders, pending/in-progress orders (statuses `pending`, `confirmed`, `preparing`, `ready for pickup`, `out for delivery`), completed orders (`delivered`).
  - Recent orders section: newest first, limited to 5, each linking to its order detail.
  - Empty state (no orders) with a clear link to browse the menu (`main.menu`).

- `GET /account/orders` → `customer.orders`
  - Requires `customer_required` guard.
  - Full order history for `user_id = current_user.id`, newest first, paginated (per_page = 10).
  - Each row: order number, date, total, payment method, payment status badge, order status badge; each row links to the order detail.
  - Pagination controls (Prev / Page X of Y / Next), reusing the existing `.pagination` pattern.

- `GET /account/orders/<order_number>` → `customer.order_detail`
  - Requires `customer_required` guard.
  - `Order.query.filter_by(order_number=order_number, user_id=current_user.id).first_or_404()` — returns 404 if the order doesn't exist or doesn't belong to the customer (no existence leakage).
  - Shows: order number, placed-on date, order items (historical `product_name`, `unit_price`, `quantity`, `subtotal`, `special_instructions`), subtotal, delivery fee, total amount, payment method, payment status badge, order status badge, delivery address, delivery instructions if any.
  - No admin forms (no status transition, no mark-as-paid).
  - A link back to order history.

**Guard** (`customer_required` in `app/customer/routes.py`):

- Not authenticated → flash "Please log in to access this page." (warning), redirect to `auth.login` with `next=request.url`.
- Is admin → flash "Admin users cannot access the customer dashboard." (warning), redirect to `admin.dashboard`.
- Otherwise proceed.

**Ownership enforcement**: every order query filters `user_id = current_user.id`. The detail route never trusts a user ID from the URL/form. Unknown or foreign order numbers yield `first_or_404()` → the project's normal 404.

**Templates** (extend `base.html`, `body_class = customer-page`):

- `customer/dashboard.html` — hero welcome, profile card, stat cards, recent orders list, empty state with "Browse Menu" link.
- `customer/order_history.html` — orders table + pagination.
- `customer/order_detail.html` — order header, items list, totals, status/payment badges, delivery address, back-to-history link.

**CSS** (`app/static/css/style.css`):

- No new CSS required: reuse `.badge-status-*`, `.badge-paid`, `.badge-pending`, `.stat-card`, `.btn`, `.table-wrap`/`.admin-table`, `.empty`, `.pagination`, and the existing `customer-card`/`customer-grid` patterns. Keep to existing classes to avoid style bloat.

**Navigation** (`app/templates/base.html`):

- Retarget the logged-in "My Account" link from `main.customer_home` to `customer.dashboard` (`/account`). The `/customer` route is left in place (unlinked) so existing links/bookmarks keep working.

**Tests** (new file `test_customer_dashboard.py`, same manual-runner style as existing suites):

- Logged-out users are redirected from `/account`, `/account/orders`, and `/account/orders/<number>` (with `next` pointing to login).
- A logged-in customer sees only their own orders (another customer's orders do not appear).
- A customer cannot view another customer's order by changing the order number → 404.
- Dashboard summary counts and recent orders (newest first, limit 5) are correct.
- Order history is newest first; pagination works (page 2 shows the next set).
- Order details show historical item/price snapshots, subtotal, delivery fee, and total.
- Customers cannot access admin order-management actions (`/admin/orders`, `/admin/orders/<n>`) → 302/403.
- Empty order history renders the empty state correctly.
- Existing suites (`test_auth.py`, `test_cart.py`, `test_orders.py`, `test_admin_orders.py`) still pass.

## What's left to the builder

- Exact `per_page` value for history pagination (recommended 10).
- Whether the dashboard "pending/in-progress" card counts all active non-final statuses (`pending` + `confirmed`/`preparing`/`ready for pickup`/`out for delivery`) versus `pending` only (recommended: all active statuses).
- Exact welcome-heading and empty-state wording.
- Whether to keep `/customer` (`customer_home`) reachable after retargeting the nav link (recommended: leave it in place, unlinked).

---

This design is ready for your approval. Once you approve it, I will implement Feature 7 only (no unrelated changes or refactors), then write the implementation plan via `superpowers:writing-plans`. If anything above is wrong or missing, tell me and I'll revise before building.