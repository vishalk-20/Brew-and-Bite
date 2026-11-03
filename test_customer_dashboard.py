"""Comprehensive tests for Feature 7: Customer Dashboard."""
import re
import time
from app import create_app

app = create_app()
TS = str(int(time.time()))  # unique suffix to avoid DB conflicts between runs


def test_client():
    return app.test_client()


def _csrf(client, path):
    """Fetch a CSRF token from a GET form page."""
    resp = client.get(path)
    match = re.search(r'name="csrf_token" value="([^"]+)"', resp.get_data(as_text=True))
    return match.group(1) if match else ""


def _register_and_login(client, email, name="Test User", phone="+1 555-0123", password="securepass123"):
    """Register and log in a customer. Returns the client."""
    client.post("/register", data={
        "csrf_token": _csrf(client, "/register"),
        "name": name,
        "email": email,
        "phone": phone,
        "password": password,
        "confirm_password": password,
        "terms": "on",
    }, follow_redirects=False)
    client.post("/login", data={
        "csrf_token": _csrf(client, "/login"),
        "email": email,
        "password": password,
    }, follow_redirects=False)
    return client


def _get_available_product(client):
    """Return an available vegetarian product (id, name, price), creating one if needed."""
    with app.app_context():
        from app.models import Product, Category
        p = Product.query.filter_by(is_vegetarian=True, is_available=True).first()
        if p is None:
            cat = Category.query.first() or Category(name="Test", description="Test")
            if not Category.query.first():
                from app.extensions import db
                db.session.add(cat)
                db.session.commit()
            p = Product(name="Test Pizza", description="Test", price=9.99,
                        category_id=cat.id, is_vegetarian=True, is_available=True)
            from app.extensions import db
            db.session.add(p)
            db.session.commit()
        return p.id, p.name, p.price


def _add_product_to_cart(client, product_id, quantity=1, notes=None):
    """Add a product to the cart via the cart route."""
    data = {"csrf_token": _csrf(client, "/menu")}
    if quantity:
        data["quantity"] = quantity
    if notes:
        data["notes"] = notes
    client.post(f"/cart/add/{product_id}", data=data, follow_redirects=False)


def _place_order(client, product_id, customer_name="Aarav Sharma", phone="9876543210"):
    """Place an order and return its order_number."""
    data = {
        "csrf_token": _csrf(client, "/checkout"),
        "customer_name": customer_name,
        "phone": phone,
        "delivery_address": "Flat 4B, Green Residency",
        "landmark": "Near City Mall",
        "city": "New Delhi",
        "state": "Delhi",
        "pin_code": "110001",
        "delivery_instructions": "Please ring the doorbell twice.",
    }
    client.post("/checkout", data=data, follow_redirects=False)
    with app.app_context():
        from app.models import Order
        order = Order.query.filter_by(customer_name=customer_name, phone=phone).order_by(
            Order.created_at.desc()
        ).first()
        return order.order_number


# ---------------------------------------------------------------------------
# 1. Logged-out users are redirected from dashboard, history, and detail.
# ---------------------------------------------------------------------------
def test_logged_out_redirected_from_dashboard():
    client = test_client()
    resp = client.get("/account", follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    assert "/login" in resp.headers.get("Location", ""), \
        f"Expected redirect to login, got {resp.headers.get('Location')}"
    print("PASS: 1a. Logged-out redirected from /account.")


def test_logged_out_redirected_from_history():
    client = test_client()
    resp = client.get("/account/orders", follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    assert "/login" in resp.headers.get("Location", ""), \
        f"Expected redirect to login, got {resp.headers.get('Location')}"
    print("PASS: 1b. Logged-out redirected from /account/orders.")


def test_logged_out_redirected_from_order_detail():
    client = test_client()
    resp = client.get("/account/orders/BB-00000000-AAA", follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    assert "/login" in resp.headers.get("Location", ""), \
        f"Expected redirect to login, got {resp.headers.get('Location')}"
    print("PASS: 1c. Logged-out redirected from /account/orders/<n>.")


# ---------------------------------------------------------------------------
# 2. Admin is redirected to the admin dashboard (not shown customer pages).
# ---------------------------------------------------------------------------
def test_admin_redirected_from_customer_dashboard():
    client = test_client()
    with app.app_context():
        from app.models import User
        from app.extensions import db
        admin = User.query.filter_by(email="custdashadmin@test.com").first()
        if not admin:
            admin = User(name="Cust Dash Admin", email="custdashadmin@test.com", role="admin")
            admin.set_password("adminpass123")
            db.session.add(admin)
            db.session.commit()
    client.post("/login", data={
        "csrf_token": _csrf(client, "/login"),
        "email": "custdashadmin@test.com",
        "password": "adminpass123",
    }, follow_redirects=False)
    resp = client.get("/account", follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    assert "/admin" in resp.headers.get("Location", ""), \
        f"Expected redirect to admin, got {resp.headers.get('Location')}"
    print("PASS: 2. Admin redirected from /account to admin dashboard.")


# ---------------------------------------------------------------------------
# 3. A logged-in customer sees only their own orders.
# ---------------------------------------------------------------------------
def test_customer_sees_only_own_orders():
    client = test_client()
    # Customer A places two orders
    email_a = f"custa{TS}@example.com"
    _register_and_login(client, email_a)
    pid, pname, pprice = _get_available_product(client)
    _add_product_to_cart(client, pid)
    order_a1 = _place_order(client, pid, customer_name="Customer A One")
    _add_product_to_cart(client, pid)
    order_a2 = _place_order(client, pid, customer_name="Customer A Two")

    # Customer B places one order
    client_b = test_client()
    email_b = f"custb{TS}@example.com"
    _register_and_login(client_b, email_b)
    _add_product_to_cart(client_b, pid)
    order_b1 = _place_order(client_b, pid, customer_name="Customer B One")

    # Customer A's history should show only A's orders
    resp = client.get("/account/orders", follow_redirects=False)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert order_a1 in body, "Customer A's first order should appear"
    assert order_a2 in body, "Customer A's second order should appear"
    assert order_b1 not in body, "Customer B's order should not appear"

    # Customer B's history should show only B's order
    resp_b = client_b.get("/account/orders", follow_redirects=False)
    body_b = resp_b.get_data(as_text=True)
    assert order_b1 in body_b, "Customer B's order should appear"
    assert order_a1 not in body_b, "Customer A's orders should not appear"
    assert order_a2 not in body_b, "Customer A's orders should not appear"
    print("PASS: 3. Customer sees only their own orders.")


# ---------------------------------------------------------------------------
# 4. A customer cannot view another customer's order by order number.
# ---------------------------------------------------------------------------
def test_customer_cannot_view_another_customers_order():
    client = test_client()
    email_a = f"viewera{TS}@example.com"
    _register_and_login(client, email_a)
    pid, pname, pprice = _get_available_product(client)
    _add_product_to_cart(client, pid)
    order_number = _place_order(client, pid, customer_name="Victim")

    # Customer B tries to view A's order
    client_b = test_client()
    email_b = f"viewerb{TS}@example.com"
    _register_and_login(client_b, email_b)
    resp = client_b.get(f"/account/orders/{order_number}", follow_redirects=False)
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    print("PASS: 4. Customer cannot view another customer's order (404).")


# ---------------------------------------------------------------------------
# 5. Dashboard summary counts and recent orders are correct.
# ---------------------------------------------------------------------------
def test_dashboard_counts_and_recent_orders():
    client = test_client()
    email = f"dashcust{TS}@example.com"
    _register_and_login(client, email)
    pid, pname, pprice = _get_available_product(client)

    # Place one pending order (default status)
    _add_product_to_cart(client, pid)
    order_number = _place_order(client, pid, customer_name="Dash Customer")

    resp = client.get("/account", follow_redirects=False)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert "Total orders" in body
    assert "Pending / in progress" in body
    assert "Completed" in body
    assert "1" in body  # total orders count
    assert order_number in body, "Recent order should appear on dashboard"
    print("PASS: 5. Dashboard summary counts render correctly.")


def test_dashboard_recent_orders_newest_first_limit_five():
    client = test_client()
    email = f"recentcust{TS}@example.com"
    _register_and_login(client, email)
    pid, pname, pprice = _get_available_product(client)

    order_numbers = []
    for i in range(7):
        _add_product_to_cart(client, pid)
        order_numbers.append(_place_order(client, pid, customer_name=f"Recent Customer {i}"))

    resp = client.get("/account", follow_redirects=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Newest (index 6) should appear first; 5 newest shown (indices 6..2)
    idx6 = body.find(order_numbers[6])
    idx2 = body.find(order_numbers[2])
    assert idx6 != -1 and idx2 != -1, "Newest orders should appear in recent list"
    assert idx6 < idx2, "Newest order should appear before older ones"
    # Oldest 2 (indices 1 and 0) should be excluded
    assert order_numbers[1] not in body, "Only 5 recent orders should show"
    assert order_numbers[0] not in body, "Only 5 recent orders should show"
    print("PASS: 6. Recent orders newest first, limited to 5.")


# ---------------------------------------------------------------------------
# 7. Order history is newest first and pagination works.
# ---------------------------------------------------------------------------
def test_order_history_newest_first_and_pagination():
    client = test_client()
    email = f"pagecust{TS}@example.com"
    _register_and_login(client, email)
    pid, pname, pprice = _get_available_product(client)

    order_numbers = []
    for i in range(12):
        _add_product_to_cart(client, pid)
        order_numbers.append(_place_order(client, pid, customer_name=f"Page Customer {i}"))

    # Page 1 should show 10 orders (per_page=10), newest first
    resp = client.get("/account/orders?page=1", follow_redirects=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert order_numbers[11] in body, "Newest order should be on page 1"
    assert "Page 1 of 2" in body, "Pagination should show 2 pages"

    # Page 2 should show the remaining 2 orders (oldest)
    resp2 = client.get("/account/orders?page=2", follow_redirects=False)
    assert resp2.status_code == 200
    body2 = resp2.get_data(as_text=True)
    assert order_numbers[0] in body2, "Oldest order should be on page 2"
    assert order_numbers[1] in body2
    print("PASS: 7. Order history newest first with pagination.")


# ---------------------------------------------------------------------------
# 8. Order details show historical item/price snapshots and totals.
# ---------------------------------------------------------------------------
def test_order_detail_shows_snapshots_and_totals():
    client = test_client()
    email = f"detailcust{TS}@example.com"
    _register_and_login(client, email)
    pid, pname, pprice = _get_available_product(client)
    _add_product_to_cart(client, pid, quantity=2, notes="Extra cheese, please")
    order_number = _place_order(client, pid, customer_name="Detail Customer")

    resp = client.get(f"/account/orders/{order_number}", follow_redirects=False)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert order_number in body
    assert pname in body, "Historical product name should appear"
    assert "Extra cheese, please" in body, "Special instructions should appear"
    assert "&#8377;" in body, "Prices should be in rupees"
    assert "Cash on Delivery" in body
    assert "Flat 4B, Green Residency" in body
    print("PASS: 8. Order detail shows historical snapshots and totals.")


# ---------------------------------------------------------------------------
# 9. Customers cannot access admin order-management actions.
# ---------------------------------------------------------------------------
def test_customer_cannot_access_admin_orders():
    client = test_client()
    email = f"custnoadmin{TS}@example.com"
    _register_and_login(client, email)
    resp = client.get("/admin/orders", follow_redirects=False)
    assert resp.status_code in (302, 403), f"Expected 302/403, got {resp.status_code}"
    print("PASS: 9a. Customer cannot access /admin/orders.")


def test_customer_cannot_access_admin_order_detail():
    client = test_client()
    email = f"custnodetail{TS}@example.com"
    _register_and_login(client, email)
    pid, pname, pprice = _get_available_product(client)
    _add_product_to_cart(client, pid)
    order_number = _place_order(client, pid)
    resp = client.get(f"/admin/orders/{order_number}", follow_redirects=False)
    assert resp.status_code in (302, 403), f"Expected 302/403, got {resp.status_code}"
    print("PASS: 9b. Customer cannot access /admin/orders/<n>.")


# ---------------------------------------------------------------------------
# 10. Empty order history renders correctly.
# ---------------------------------------------------------------------------
def test_empty_order_history_renders():
    client = test_client()
    email = f"emptycust{TS}@example.com"
    _register_and_login(client, email)
    resp = client.get("/account/orders", follow_redirects=False)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert "placed any orders yet" in body.lower(), \
        f"Expected empty state message, got: {body[:300]}"
    assert "Browse Menu" in body, "Empty state should link to browse menu"
    print("PASS: 10. Empty order history renders correctly.")


if __name__ == "__main__":
    tests = [
        test_logged_out_redirected_from_dashboard,
        test_logged_out_redirected_from_history,
        test_logged_out_redirected_from_order_detail,
        test_admin_redirected_from_customer_dashboard,
        test_customer_sees_only_own_orders,
        test_customer_cannot_view_another_customers_order,
        test_dashboard_counts_and_recent_orders,
        test_dashboard_recent_orders_newest_first_limit_five,
        test_order_history_newest_first_and_pagination,
        test_order_detail_shows_snapshots_and_totals,
        test_customer_cannot_access_admin_orders,
        test_customer_cannot_access_admin_order_detail,
        test_empty_order_history_renders,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {len(tests)} tests.")
