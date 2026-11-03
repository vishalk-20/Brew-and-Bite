# Admin Order Management — Design Doc

Date: 2026-11-03
Topic: Feature 6 — Admin Order Management

## Intent and the why

Brew & Bite lets customers place vegetarian orders that are captured as `Order` + `OrderItem` records. Admin users currently have no way to view, search, or act on those orders once placed. Feature 6 gives admins a dedicated orders workspace: list all orders, drill into an order's details, move an order through its lifecycle, and mark Cash on Delivery orders as paid. This lets staff run the kitchen/delivery operation from the admin panel instead of inspecting the database directly.

## Goals

- Admins can list all orders, newest first, with search and status/payment filters and pagination.
- Admins can view a single order's customer details, line items (with historical names/prices), and summary.
- Admins can transition an order's status forward through the allowed chain, with cancellation permitted from any non-final state; delivered and cancelled orders are final.
- Admins can mark COD orders as paid; payment status is managed separately from order status.
- All validation happens server-side; invalid transitions/statuses are rejected with a friendly flash message.
- Customers cannot access any admin order route.
- Existing tests keep passing; no checkout/payment/email/SMS changes.

## Non-goals

- Online payment processing (orders remain COD only).
- Customer-facing order tracking or history pages beyond what exists.
- Email or SMS notifications on status/payment changes.
- Deleting or modifying historical orders or order items.
- Adding new database tables or altering existing columns.

## Anti-goals (failure even if it technically works)

- A customer can reach `/admin/orders` or `/admin/orders/<n>` and see another customer's data.
- An order jumps from `Pending` to `Delivered` or moves backward.
- A `Delivered` or `Cancelled` order is changed again.
- A non-COD order's payment status is flipped to `Paid` through this feature.
- Historical product names/prices on an order item are replaced by current product data.

## Acceptance criteria

- Payment updates: only allow marking an order paid if it is COD and not already paid; reject other payment methods and duplicate "already paid" updates with a clear message.
- Invalid or missing orders: unknown order numbers return the existing not-found behavior; invalid status or payment requests show a friendly message without changing the order.

## Constraints

- Reuse existing `Order` and `OrderItem` models; no new tables, no column changes.
- Reuse existing admin blueprint, `admin_required` guard, session-based CSRF, flash categories, and admin shell template.
- Prices formatted as `&#8377;{{ "%.2f"|format(price) }}` (₹, two decimals).
- CSRF token named `csrf_token`, validated in `_csrf_valid()` per blueprint.
- Orders blueprint has no `url_prefix`; admin blueprint is mounted at `/admin`.
- Delivery fee read from `current_app.config["DELIVERY_FEE"]`.
- No online payments, no email/SMS.

## Approaches considered

1. **Status logic as methods on the `Order` model** (chosen).
   - Add `ALLOWED_TRANSITIONS`, `can_transition_to(new_status)`, `transition_to(new_status)`.
   - Rules live with the data, reusable, unit-testable without HTTP.
   - Routes stay thin: call `order.transition_to(...)` and flash the result.
2. **Status logic inline in the admin routes** (rejected).
   - Duplicates the matrix if reused elsewhere; harder to unit-test in isolation.
3. **Database CHECK constraint / enum** (rejected).
   - Overkill for SQLite, opaque errors, hard to change.

## How it gets built (decisions made)

**Model** (`app/models.py`):
- `Order.ALLOWED_TRANSITIONS = { ... }` mapping current status -> set of allowed next statuses.
  - Pending -> {Confirmed, Cancelled}
  - Confirmed -> {Preparing, Cancelled}
  - Preparing -> {Ready for Pickup, Cancelled}
  - Ready for Pickup -> {Out for Delivery, Cancelled}
  - Out for Delivery -> {Delivered, Cancelled}
  - Delivered -> {} (final)
  - Cancelled -> {} (final)
- `can_transition_to(new_status)` returns True if the transition is allowed.
- `transition_to(new_status)` sets `order_status` if allowed, else raises `ValueError` with a friendly message.
- Cancellation is allowed from any non-final state (Pending, Confirmed, Preparing, Ready for Pickup, Out for Delivery).

**Routes** (in `app/admin/routes.py`, mounted under `/admin`):
- `GET /admin/orders` — list orders with search (order number, customer name, phone), status filter, payment-status filter, pagination; newest first. Preserves query params across pagination pages.
- `GET /admin/orders/<order_number>` — order details: customer block, order items (historical name/price/subtotal/instructions), order summary (subtotal, delivery fee, total, payment method/status, order status, date/time).
- `POST /admin/orders/<order_number>/status` — CSRF-protected; reads `new_status` from form; calls `order.transition_to(...)`; flashes success or validation error; redirects back to the order detail.
- `POST /admin/orders/<order_number>/payment` — CSRF-protected; only COD orders may be marked paid; validates current payment status; sets `payment_status = "paid"`; flashes success or error; redirects back to order detail.

**Dashboard** (`app/admin/routes.py` dashboard + template):
- Add order stat cards: Total Orders, Pending Orders, Orders in Progress (all statuses except delivered/cancelled/pending), Delivered Orders.
- Optional: five most recent orders with a "View All Orders" link.

**Templates** (extend `admin/base.html`):
- `admin/orders_list.html` — toolbar (search + status filter + payment filter), orders table, pagination.
- `admin/order_detail.html` — customer details, order items table, order summary, status dropdown form, payment mark-paid form.
- Update `admin/dashboard.html` with order stat cards + recent orders.

**CSS** (`app/static/css/style.css`):
- Add status badge colors: pending (amber), confirmed (blue), preparing (purple), ready for pickup (teal), out for delivery (blue), delivered (green), cancelled (red). Reuse existing `.badge` pattern.

**Tests** (new file or added to `test_orders.py`):
- Model-level: every valid transition succeeds; every invalid transition raises; delivered/cancelled are final; cancellation allowed from non-final states.
- Route-level (via test client as admin): orders list loads; customer redirected/403; search by number/name/phone; status filter; payment filter; pagination; status update valid/invalid; payment mark-paid valid/non-COD rejected; order detail shows historical prices.
- Existing `test_auth.py`, `test_cart.py`, `test_orders.py` still pass.

## What's left to the builder

- Exact CSS hex values for the seven status badges (amber/blue/purple/teal/green/red), chosen to harmonize with the existing coffee-brown palette.
- Whether the "Orders in Progress" stat counts `Preparing` + `Ready for Pickup` + `Out for Delivery` (recommended) or includes `Confirmed`.
- Whether to create a new `test_admin_orders.py` or append to `test_orders.py` (recommended: new file for clarity).
- Confirmation that the admin sidebar's new "Orders" nav item is the desired label/placement.

---

This design is ready for your approval. Once you approve it, I'll implement Feature 6. If anything above is wrong or missing, tell me and I'll revise before building.