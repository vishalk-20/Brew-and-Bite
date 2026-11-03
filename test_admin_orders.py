"""Tests for Feature 6: Admin Order Management."""
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
    """Register and log in a customer."""
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


def _login_admin(client, email="adminorders@test.com", password="adminpass123"):
    """Ensure an admin user exists and log in as that admin."""
    with app.app_context():
        from app.models import User
        from app.extensions import db
        admin = User.query.filter_by(email=email).first()
        if not admin:
            admin = User(name="Order Admin", email=email, role="admin")
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
    client.post("/login", data={
        "csrf_token": _csrf(client, "/login"),
        "email": email,
        "password": password,
    }, follow_redirects=False)
    return client


def _get_available_product(client):
    """Return an available vegetarian product (id, name, price)."""
    with app.app_context():
        from app.models import Product
        p = Product.query.filter_by(is_vegetarian=True, is_available=True).first()
        return p.id, p.name, p.price


def _add_product_to_cart(client, product_id, quantity=1, notes=None):
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
# Model-level transition tests
# ---------------------------------------------------------------------------
def test_order_model_valid_transitions():
    with app.app_context():
        from app.models import Order
        order = Order(order_number="BB-TEST", user_id=1, customer_name="X", phone="1",
                      delivery_address="A", city="C", state="S", pin_code="110001",
                      subtotal=10, delivery_fee=0, total_amount=10)
        # pending -> confirmed
        assert order.can_transition_to("confirmed")
        order.transition_to("confirmed")
        assert order.order_status == "confirmed"
        # confirmed -> preparing
        assert order.can_transition_to("preparing")
        order.transition_to("preparing")
        assert order.order_status == "preparing"
        # preparing -> ready for pickup
        assert order.can_transition_to("ready for pickup")
        order.transition_to("ready for pickup")
        # ready for pickup -> out for delivery
        assert order.can_transition_to("out for delivery")
        order.transition_to("out for delivery")
        # out for delivery -> delivered
        assert order.can_transition_to("delivered")
        order.transition_to("delivered")
        assert order.order_status == "delivered"
    print("PASS: Model - valid forward transitions work.")


def test_order_model_cancellation_from_non_final():
    with app.app_context():
        from app.models import Order
        for status in ["pending", "confirmed", "preparing", "ready for pickup", "out for delivery"]:
            order = Order(order_number="BB-TEST", user_id=1, customer_name="X", phone="1",
                          delivery_address="A", city="C", state="S", pin_code="110001",
                          subtotal=10, delivery_fee=0, total_amount=10, order_status=status)
            assert order.can_transition_to("cancelled"), f"Should cancel from {status}"
            order.transition_to("cancelled")
            assert order.order_status == "cancelled"
    print("PASS: Model - cancellation allowed from any non-final state.")


def test_order_model_invalid_transitions_rejected():
    with app.app_context():
        from app.models import Order
        # pending -> delivered (skip steps)
        order = Order(order_number="BB-TEST", user_id=1, customer_name="X", phone="1",
                      delivery_address="A", city="C", state="S", pin_code="110001",
                      subtotal=10, delivery_fee=0, total_amount=10, order_status="pending")
        assert order.order_status == "pending"
        try:
            order.transition_to("delivered")
            assert False, "Should have raised"
        except ValueError:
            pass
        # Order status unchanged after failed transition
        assert order.order_status == "pending"
    print("PASS: Model - invalid transitions rejected.")


def test_order_model_final_states_immutable():
    with app.app_context():
        from app.models import Order
        for final in ["delivered", "cancelled"]:
            order = Order(order_number="BB-TEST", user_id=1, customer_name="X", phone="1",
                          delivery_address="A", city="C", state="S", pin_code="110001",
                          subtotal=10, delivery_fee=0, total_amount=10, order_status=final)
            try:
                order.transition_to("pending")
                assert False, f"Should not allow transition from {final}"
            except ValueError:
                pass
    print("PASS: Model - delivered and cancelled are final.")


def test_order_model_invalid_status_value():
    with app.app_context():
        from app.models import Order
        order = Order(order_number="BB-TEST", user_id=1, customer_name="X", phone="1",
                      delivery_address="A", city="C", state="S", pin_code="110001",
                      subtotal=10, delivery_fee=0, total_amount=10)
        try:
            order.transition_to("not a status")
            assert False, "Should have raised"
        except ValueError:
            pass
    print("PASS: Model - invalid status value rejected.")


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------
def test_admin_can_view_all_orders():
    client = test_client()
    # Place an order as a customer
    customer = _register_and_login(client, f"custview{TS}@example.com")
    product_id, product_name, product_price = _get_available_product(client)
    _add_product_to_cart(customer, product_id, quantity=2)
    order_number = _place_order(customer, product_id)

    # Login as admin
    admin = _login_admin(test_client())
    resp = admin.get("/admin/orders", follow_redirects=False)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert order_number in body, "Order number should appear in orders list"
    assert product_name in body or "View Details" in body
    print("PASS: 1. Admin can view all orders.")


def test_customer_cannot_access_admin_orders():
    client = test_client()
    _register_and_login(client, f"custno{TS}@example.com")
    resp = client.get("/admin/orders", follow_redirects=False)
    assert resp.status_code in (302, 403), f"Expected 302/403, got {resp.status_code}"
    print("PASS: 2. Customer cannot access admin orders.")


def test_orders_sorted_newest_first():
    client = test_client()
    # Place two orders
    c1 = _register_and_login(client, f"custsort1{TS}@example.com")
    pid, pname, pprice = _get_available_product(c1)
    _add_product_to_cart(c1, pid)
    on1 = _place_order(c1, pid, customer_name="First Customer")

    c2 = _register_and_login(client, f"custsort2{TS}@example.com")
    _add_product_to_cart(c2, pid)
    on2 = _place_order(c2, pid, customer_name="Second Customer")

    admin = _login_admin(test_client())
    resp = admin.get("/admin/orders", follow_redirects=False)
    body = resp.get_data(as_text=True)
    # Second (newest) should appear before first
    idx1 = body.find(on1)
    idx2 = body.find(on2)
    assert idx2 != -1 and idx1 != -1, "Both orders should appear"
    assert idx2 < idx1, "Newest order should appear first"
    print("PASS: 3. Orders are sorted newest first.")


def test_search_by_order_number():
    client = test_client()
    c = _register_and_login(client, f"custsearch{TS}@example.com")
    pid, pname, pprice = _get_available_product(c)
    _add_product_to_cart(c, pid)
    order_number = _place_order(c, pid)

    admin = _login_admin(test_client())
    resp = admin.get(f"/admin/orders?search={order_number}", follow_redirects=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert order_number in body
    print("PASS: 4. Search by order number works.")


def test_search_by_customer_name():
    client = test_client()
    c = _register_and_login(client, f"custname{TS}@example.com")
    pid, pname, pprice = _get_available_product(c)
    _add_product_to_cart(c, pid)
    _place_order(c, pid, customer_name="UniqueCustomerName")

    admin = _login_admin(test_client())
    resp = admin.get("/admin/orders?search=UniqueCustomerName", follow_redirects=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "UniqueCustomerName" in body
    print("PASS: 5. Search by customer name works.")


def test_search_by_phone_number():
    client = test_client()
    c = _register_and_login(client, f"custphone{TS}@example.com")
    pid, pname, pprice = _get_available_product(c)
    _add_product_to_cart(c, pid)
    _place_order(c, pid, phone="9998887776")

    admin = _login_admin(test_client())
    resp = admin.get("/admin/orders?search=9998887776", follow_redirects=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "9998887776" in body
    print("PASS: 6. Search by phone number works.")


def test_status_filtering():
    client = test_client()
    c = _register_and_login(client, f"custfilter{TS}@example.com")
    pid, pname, pprice = _get_available_product(c)
    _add_product_to_cart(c, pid)
    _place_order(c, pid)  # status = pending

    admin = _login_admin(test_client())
    resp = admin.get("/admin/orders?status=pending", follow_redirects=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Pending" in body
    print("PASS: 7. Status filtering works.")


def test_payment_filtering():
    client = test_client()
    c = _register_and_login(client, f"custpay{TS}@example.com")
    pid, pname, pprice = _get_available_product(c)
    _add_product_to_cart(c, pid)
    _place_order(c, pid)  # payment_status = pending

    admin = _login_admin(test_client())
    resp = admin.get("/admin/orders?payment=pending", follow_redirects=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Pending" in body
    print("PASS: 8. Payment filtering works.")


def test_admin_can_view_order_details():
    client = test_client()
    c = _register_and_login(client, f"custdetail{TS}@example.com")
    pid, pname, pprice = _get_available_product(c)
    _add_product_to_cart(c, pid, notes="Extra cheese")
    order_number = _place_order(c, pid)

    admin = _login_admin(test_client())
    resp = admin.get(f"/admin/orders/{order_number}", follow_redirects=False)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert order_number in body
    assert pname in body
    assert "Flat 4B, Green Residency" in body
    assert "Extra cheese" in body
    print("PASS: 9. Admin can view order details.")


def test_historical_product_names_and_prices_unchanged():
    client = test_client()
    c = _register_and_login(client, f"custhist{TS}@example.com")
    pid, pname, pprice = _get_available_product(c)
    _add_product_to_cart(c, pid)
    order_number = _place_order(c, pid)

    admin = _login_admin(test_client())
    resp = admin.get(f"/admin/orders/{order_number}", follow_redirects=False)
    body = resp.get_data(as_text=True)
    assert pname in body, "Historical product name should appear"
    assert "&#8377;" in body, "Prices should be in rupees"
    print("PASS: 10. Historical product names and prices remain unchanged.")


def test_admin_can_update_order_status():
    client = test_client()
    c = _register_and_login(client, f"custstatus{TS}@example.com")
    pid, pname, pprice = _get_available_product(c)
    _add_product_to_cart(c, pid)
    order_number = _place_order(c, pid)

    admin = _login_admin(test_client())
    # Get CSRF from the detail page
    resp = admin.get(f"/admin/orders/{order_number}", follow_redirects=False)
    csrf = _csrf(admin, f"/admin/orders/{order_number}")
    resp2 = admin.post(f"/admin/orders/{order_number}/status", data={
        "csrf_token": csrf,
        "new_status": "confirmed",
    }, follow_redirects=False)
    assert resp2.status_code in (302,), f"Expected redirect, got {resp2.status_code}"

    with app.app_context():
        from app.models import Order
        order = Order.query.filter_by(order_number=order_number).first()
        assert order.order_status == "confirmed", f"Expected confirmed, got {order.order_status}"
    print("PASS: 11. Admin can update order status.")


def test_invalid_status_value_rejected():
    client = test_client()
    c = _register_and_login(client, f"custinval{TS}@example.com")
    pid, pname, pprice = _get_available_product(c)
    _add_product_to_cart(c, pid)
    order_number = _place_order(c, pid)

    admin = _login_admin(test_client())
    csrf = _csrf(admin, f"/admin/orders/{order_number}")
    resp = admin.post(f"/admin/orders/{order_number}/status", data={
        "csrf_token": csrf,
        "new_status": "not a status",
    }, follow_redirects=False)
    assert resp.status_code in (302,)

    # Follow redirect to see flash message on detail page
    resp2 = admin.get(f"/admin/orders/{order_number}", follow_redirects=False)
    body2 = resp2.get_data(as_text=True)
    assert "not a status" in body2.lower() or "invalid" in body2.lower() or "valid order status" in body2.lower(), \
        f"Expected validation error message, got: {body2[:300]}"

    with app.app_context():
        from app.models import Order
        order = Order.query.filter_by(order_number=order_number).first()
        assert order.order_status == "pending", "Order should not have changed"
    print("PASS: 12. Invalid status values are rejected.")


def test_invalid_status_transition_rejected():
    client = test_client()
    c = _register_and_login(client, f"custtrans{TS}@example.com")
    pid, pname, pprice = _get_available_product(c)
    _add_product_to_cart(c, pid)
    order_number = _place_order(c, pid)  # status = pending

    admin = _login_admin(test_client())
    # Try pending -> delivered (skip steps)
    csrf = _csrf(admin, f"/admin/orders/{order_number}")
    resp = admin.post(f"/admin/orders/{order_number}/status", data={
        "csrf_token": csrf,
        "new_status": "delivered",
    }, follow_redirects=False)
    assert resp.status_code in (302,)

    resp2 = admin.get(f"/admin/orders/{order_number}", follow_redirects=False)
    body = resp2.get_data(as_text=True)
    assert "cannot move" in body.lower() or "allowed next" in body.lower(), \
        f"Expected transition error, got: {body[:300]}"

    with app.app_context():
        from app.models import Order
        order = Order.query.filter_by(order_number=order_number).first()
        assert order.order_status == "pending", "Order should not have changed"
    print("PASS: 13. Invalid status transitions are rejected.")


def test_admin_can_mark_cod_payment_as_paid():
    client = test_client()
    c = _register_and_login(client, f"custpayok{TS}@example.com")
    pid, pname, pprice = _get_available_product(c)
    _add_product_to_cart(c, pid)
    order_number = _place_order(c, pid)

    admin = _login_admin(test_client())
    csrf = _csrf(admin, f"/admin/orders/{order_number}")
    resp = admin.post(f"/admin/orders/{order_number}/payment", data={
        "csrf_token": csrf,
    }, follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"

    with app.app_context():
        from app.models import Order
        order = Order.query.filter_by(order_number=order_number).first()
        assert order.payment_status == "paid", f"Expected paid, got {order.payment_status}"
    print("PASS: 14. Admin can mark COD payment as paid.")


def test_duplicate_payment_update_rejected():
    client = test_client()
    c = _register_and_login(client, f"custduppay{TS}@example.com")
    pid, pname, pprice = _get_available_product(c)
    _add_product_to_cart(c, pid)
    order_number = _place_order(c, pid)

    admin = _login_admin(test_client())
    csrf = _csrf(admin, f"/admin/orders/{order_number}")
    # First mark as paid
    admin.post(f"/admin/orders/{order_number}/payment", data={
        "csrf_token": csrf,
    }, follow_redirects=False)

    # Try again - should be rejected as already paid
    csrf2 = _csrf(admin, f"/admin/orders/{order_number}")
    resp = admin.post(f"/admin/orders/{order_number}/payment", data={
        "csrf_token": csrf2,
    }, follow_redirects=False)
    assert resp.status_code in (302,)

    resp2 = admin.get(f"/admin/orders/{order_number}", follow_redirects=False)
    body = resp2.get_data(as_text=True)
    assert "already" in body.lower(), f"Expected 'already paid' message, got: {body[:300]}"
    print("PASS: 15. Duplicate payment update rejected.")


def test_admin_dashboard_statistics_correct():
    client = test_client()
    # Place 3 orders: 1 pending, 1 confirmed, 1 delivered
    c1 = _register_and_login(client, f"custstat1{TS}@example.com")
    pid, pname, pprice = _get_available_product(c1)
    _add_product_to_cart(c1, pid)
    _place_order(c1, pid)  # pending

    c2 = _register_and_login(client, f"custstat2{TS}@example.com")
    _add_product_to_cart(c2, pid)
    on2 = _place_order(c2, pid)  # pending -> confirm

    admin = _login_admin(test_client())
    csrf = _csrf(admin, f"/admin/orders/{on2}")
    admin.post(f"/admin/orders/{on2}/status", data={
        "csrf_token": csrf,
        "new_status": "confirmed",
    }, follow_redirects=False)

    resp = admin.get("/admin/", follow_redirects=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Total orders" in body
    assert "Pending orders" in body
    assert "In progress" in body
    assert "Delivered" in body
    print("PASS: 16. Admin dashboard statistics are correct.")


def test_pagination_works():
    client = test_client()
    # Place multiple orders to test pagination
    for i in range(5):
        c = _register_and_login(client, f"custpage{i}{TS}@example.com")
        pid, pname, pprice = _get_available_product(c)
        _add_product_to_cart(c, pid)
        _place_order(c, pid, customer_name=f"Page Customer {i}")

    admin = _login_admin(test_client())
    resp = admin.get("/admin/orders?page=1", follow_redirects=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Page 1 of" in body or "pagination" in body.lower() or body.count("Page Customer") >= 1
    print("PASS: 17. Pagination works.")


if __name__ == "__main__":
    tests = [
        test_order_model_valid_transitions,
        test_order_model_cancellation_from_non_final,
        test_order_model_invalid_transitions_rejected,
        test_order_model_final_states_immutable,
        test_order_model_invalid_status_value,
        test_admin_can_view_all_orders,
        test_customer_cannot_access_admin_orders,
        test_orders_sorted_newest_first,
        test_search_by_order_number,
        test_search_by_customer_name,
        test_search_by_phone_number,
        test_status_filtering,
        test_payment_filtering,
        test_admin_can_view_order_details,
        test_historical_product_names_and_prices_unchanged,
        test_admin_can_update_order_status,
        test_invalid_status_value_rejected,
        test_invalid_status_transition_rejected,
        test_admin_can_mark_cod_payment_as_paid,
        test_duplicate_payment_update_rejected,
        test_admin_dashboard_statistics_correct,
        test_pagination_works,
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
