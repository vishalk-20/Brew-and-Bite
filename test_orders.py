"""Comprehensive tests for the checkout and order placement feature (Feature 5)."""
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
    """Helper: register and log in a customer. Returns the client."""
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


def _add_product_to_cart(client, product_id, quantity=1, notes=None):
    """Add a product to the cart via the cart route."""
    data = {"csrf_token": _csrf(client, "/menu")}
    if quantity:
        data["quantity"] = quantity
    if notes:
        data["notes"] = notes
    client.post(f"/cart/add/{product_id}", data=data, follow_redirects=False)


def _get_available_product(client):
    """Return an available vegetarian product (id, name, price)."""
    with app.app_context():
        from app.models import Product
        p = Product.query.filter_by(is_vegetarian=True, is_available=True).first()
        return p.id, p.name, p.price


def _checkout_form_data(**overrides):
    data = {
        "csrf_token": "",  # filled in by caller
        "customer_name": "Aarav Sharma",
        "phone": "9876543210",
        "delivery_address": "Flat 4B, Green Residency",
        "landmark": "Near City Mall",
        "city": "New Delhi",
        "state": "Delhi",
        "pin_code": "110001",
        "delivery_instructions": "Please ring the doorbell twice.",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# 1. Customer can access checkout when logged in (with items in cart).
# ---------------------------------------------------------------------------
def test_logged_in_customer_can_access_checkout():
    client = test_client()
    email = f"checkoutaccess{TS}@example.com"
    _register_and_login(client, email)
    product_id, product_name, product_price = _get_available_product(client)
    _add_product_to_cart(client, product_id, quantity=2)
    resp = client.get("/checkout", follow_redirects=False)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert "Checkout" in body, "Checkout heading should be present"
    assert product_name in body, "Ordered product should appear in summary"
    assert "Cash on Delivery" in body, "Payment method should be shown"
    print("PASS: 1. Customer can access checkout when logged in.")


# ---------------------------------------------------------------------------
# 2. Logged-out visitor is redirected to login.
# ---------------------------------------------------------------------------
def test_logged_out_visitor_redirected_to_login():
    client = test_client()
    resp = client.get("/checkout", follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    assert "/login" in resp.headers.get("Location", ""), \
        f"Expected redirect to login, got {resp.headers.get('Location')}"
    print("PASS: 2. Logged-out visitor is redirected to login.")


# ---------------------------------------------------------------------------
# 3. Empty cart cannot be checked out.
# ---------------------------------------------------------------------------
def test_empty_cart_cannot_be_checked_out():
    client = test_client()
    email = f"emptycart{TS}@example.com"
    _register_and_login(client, email)
    resp = client.get("/checkout", follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    assert "/cart" in resp.headers.get("Location", ""), \
        f"Expected redirect to cart, got {resp.headers.get('Location')}"
    print("PASS: 3. Empty cart cannot be checked out.")


# ---------------------------------------------------------------------------
# 4. Customer can submit valid delivery details and place an order.
# ---------------------------------------------------------------------------
def test_valid_checkout_places_order():
    client = test_client()
    email = f"validorder{TS}@example.com"
    _register_and_login(client, email)
    product_id, product_name, product_price = _get_available_product(client)
    _add_product_to_cart(client, product_id, quantity=2, notes="Extra cheese, please")

    resp = client.post("/checkout", data=_checkout_form_data(csrf_token=_csrf(client, "/checkout")),
                       follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    assert "/orders/" in resp.headers.get("Location", ""), \
        f"Expected redirect to confirmation, got {resp.headers.get('Location')}"

    with app.app_context():
        from app.models import Order, OrderItem, Cart, CartItem
        user = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email).first()
        order = Order.query.filter_by(user_id=user.id).first()
        assert order is not None, "Order should be saved"
        assert order.order_status == "pending", f"Expected pending, got {order.order_status}"
        assert order.payment_status == "pending", f"Expected pending, got {order.payment_status}"
        assert order.payment_method == "cod", f"Expected cod, got {order.payment_method}"
        assert order.customer_name == "Aarav Sharma"
        assert order.phone == "9876543210"
        assert order.city == "New Delhi"
        assert order.pin_code == "110001"
        assert order.delivery_instructions == "Please ring the doorbell twice."

        items = OrderItem.query.filter_by(order_id=order.id).all()
        assert len(items) == 1, f"Expected 1 order item, got {len(items)}"
        item = items[0]
        assert item.product_name == product_name, f"Expected {product_name}, got {item.product_name}"
        assert item.unit_price == product_price, f"Expected {product_price}, got {item.unit_price}"
        assert item.quantity == 2
        assert item.subtotal == product_price * 2
        assert item.special_instructions == "Extra cheese, please"

        # Cart should be cleared after successful order
        cart = Cart.query.filter_by(user_id=user.id).first()
        assert cart is not None
        assert cart.item_count == 0, "Cart should be cleared after order placement"
    print("PASS: 4. Customer can submit valid delivery details and place an order.")


# ---------------------------------------------------------------------------
# 5. Invalid phone number is rejected.
# ---------------------------------------------------------------------------
def test_invalid_phone_rejected():
    client = test_client()
    email = f"badphone{TS}@example.com"
    _register_and_login(client, email)
    product_id, product_name, product_price = _get_available_product(client)
    _add_product_to_cart(client, product_id)

    data = _checkout_form_data(csrf_token=_csrf(client, "/checkout"), phone="123")
    resp = client.post("/checkout", data=data, follow_redirects=False)
    assert resp.status_code == 200, f"Expected 200 (re-render), got {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert "valid indian phone number" in body.lower(), \
        f"Expected phone validation error, got: {body[:500]}"
    # Form values preserved
    assert "Aarav Sharma" in body, "Name should be preserved"
    assert "123" in body, "Invalid phone should be preserved"
    print("PASS: 5. Invalid phone number is rejected.")


# ---------------------------------------------------------------------------
# 6. Invalid PIN code is rejected.
# ---------------------------------------------------------------------------
def test_invalid_pin_rejected():
    client = test_client()
    email = f"badpin{TS}@example.com"
    _register_and_login(client, email)
    product_id, product_name, product_price = _get_available_product(client)
    _add_product_to_cart(client, product_id)

    data = _checkout_form_data(csrf_token=_csrf(client, "/checkout"), pin_code="12345")
    resp = client.post("/checkout", data=data, follow_redirects=False)
    assert resp.status_code == 200, f"Expected 200 (re-render), got {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert "PIN code must be a 6-digit number" in body, \
        f"Expected PIN validation error, got: {body[:500]}"
    print("PASS: 6. Invalid PIN code is rejected.")


# ---------------------------------------------------------------------------
# 7. Unavailable products cannot be ordered.
# ---------------------------------------------------------------------------
def test_unavailable_product_cannot_be_ordered():
    client = test_client()
    email = f"unavorder{TS}@example.com"
    _register_and_login(client, email)
    with app.app_context():
        from app.models import Product, Category
        cat = Category.query.first()
        p = Product.query.filter_by(is_vegetarian=True, is_available=False).first()
        if p is None:
            p = Product(name="Unavailable Item", description="Test", price=9.99,
                        category_id=cat.id, is_vegetarian=True, is_available=False)
            from app.extensions import db
            db.session.add(p)
            db.session.commit()
        product_id = p.id
    _add_product_to_cart(client, product_id)
    resp = client.get("/checkout", follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    assert "/cart" in resp.headers.get("Location", "")
    print("PASS: 7. Unavailable products cannot be ordered.")


# ---------------------------------------------------------------------------
# 8. Non-vegetarian products cannot be ordered.
# ---------------------------------------------------------------------------
def test_non_vegetarian_product_cannot_be_ordered():
    client = test_client()
    email = f"nonvegorder{TS}@example.com"
    _register_and_login(client, email)
    with app.app_context():
        from app.models import Product, Category
        cat = Category.query.first()
        p = Product.query.filter_by(is_vegetarian=False).first()
        if p is None:
            p = Product(name="Non-Veg Item", description="Test", price=9.99,
                        category_id=cat.id, is_vegetarian=False, is_available=True)
            from app.extensions import db
            db.session.add(p)
            db.session.commit()
        product_id = p.id
    _add_product_to_cart(client, product_id)
    resp = client.get("/checkout", follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    assert "/cart" in resp.headers.get("Location", "")
    print("PASS: 8. Non-vegetarian products cannot be ordered.")


# ---------------------------------------------------------------------------
# 9. Prices and totals are calculated on the backend (not trusted from frontend).
# ---------------------------------------------------------------------------
def test_prices_calculated_on_backend():
    client = test_client()
    email = f"backendprice{TS}@example.com"
    _register_and_login(client, email)
    product_id, product_name, product_price = _get_available_product(client)
    _add_product_to_cart(client, product_id, quantity=3)

    # Attempt to submit a bogus total via a hidden field (should be ignored).
    data = _checkout_form_data(csrf_token=_csrf(client, "/checkout"))
    data["total_amount"] = "0.01"  # bogus
    data["subtotal"] = "0.01"      # bogus
    resp = client.post("/checkout", data=data, follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"

    with app.app_context():
        from app.models import Order
        user = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email).first()
        order = Order.query.filter_by(user_id=user.id).first()
        expected_total = (product_price * 3) + __import__('decimal').Decimal("40.00")
        assert order.total_amount == expected_total, \
            f"Expected {expected_total}, got {order.total_amount} (frontend total was ignored)"
        assert order.subtotal == product_price * 3
    print("PASS: 9. Prices and totals are calculated on the backend.")


# ---------------------------------------------------------------------------
# 10-11. Order saved in DB; items preserve product names and prices.
# ---------------------------------------------------------------------------
def test_order_and_items_persist_with_snapshots():
    client = test_client()
    email = f"snapshot{TS}@example.com"
    _register_and_login(client, email)
    product_id, product_name, product_price = _get_available_product(client)
    _add_product_to_cart(client, product_id, quantity=1)
    client.post("/checkout", data=_checkout_form_data(csrf_token=_csrf(client, "/checkout")),
                follow_redirects=False)

    with app.app_context():
        from app.models import Order, OrderItem
        user = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email).first()
        order = Order.query.filter_by(user_id=user.id).first()
        assert order is not None
        assert order.order_number.startswith("BB-")
        item = OrderItem.query.filter_by(order_id=order.id).first()
        assert item.product_name == product_name
        assert item.unit_price == product_price
        assert item.product_id == product_id
    print("PASS: 10-11. Order saved and items preserve product name/price snapshots.")


# ---------------------------------------------------------------------------
# 12. Special instructions are preserved.
# ---------------------------------------------------------------------------
def test_special_instructions_preserved():
    client = test_client()
    email = f"instructions{TS}@example.com"
    _register_and_login(client, email)
    product_id, product_name, product_price = _get_available_product(client)
    notes = "No onions, extra coriander"
    _add_product_to_cart(client, product_id, notes=notes)
    client.post("/checkout", data=_checkout_form_data(csrf_token=_csrf(client, "/checkout")),
                follow_redirects=False)
    with app.app_context():
        from app.models import Order, OrderItem
        user = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email).first()
        order = Order.query.filter_by(user_id=user.id).first()
        item = OrderItem.query.filter_by(order_id=order.id).first()
        assert item.special_instructions == notes
        assert order.delivery_instructions == "Please ring the doorbell twice."
    print("PASS: 12. Special instructions are preserved.")


# ---------------------------------------------------------------------------
# 13. Cart is cleared only after successful order placement.
# ---------------------------------------------------------------------------
def test_cart_cleared_after_successful_order():
    client = test_client()
    email = f"cartclear{TS}@example.com"
    _register_and_login(client, email)
    product_id, product_name, product_price = _get_available_product(client)
    _add_product_to_cart(client, product_id, quantity=2)
    client.post("/checkout", data=_checkout_form_data(csrf_token=_csrf(client, "/checkout")),
                follow_redirects=False)
    with app.app_context():
        from app.models import Cart, CartItem
        user = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email).first()
        cart = Cart.query.filter_by(user_id=user.id).first()
        remaining = CartItem.query.filter_by(cart_id=cart.id).all()
        assert len(remaining) == 0, "Cart items should be deleted after order"
    print("PASS: 13. Cart is cleared after successful order placement.")


# ---------------------------------------------------------------------------
# 14. Order confirmation displays correctly.
# ---------------------------------------------------------------------------
def test_order_confirmation_displays_correctly():
    client = test_client()
    email = f"confirm{TS}@example.com"
    _register_and_login(client, email)
    product_id, product_name, product_price = _get_available_product(client)
    _add_product_to_cart(client, product_id, quantity=1, notes="Extra cheese")
    client.post("/checkout", data=_checkout_form_data(csrf_token=_csrf(client, "/checkout")),
                follow_redirects=False)

    with app.app_context():
        from app.models import Order
        user = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email).first()
        order = Order.query.filter_by(user_id=user.id).first()
        order_number = order.order_number

    resp = client.get(f"/orders/{order_number}/confirmation", follow_redirects=False)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert "Order confirmed" in body or "order confirmed" in body.lower()
    assert order_number in body
    assert product_name in body
    assert "&#8377;" in body, "Prices should be in rupees"
    assert "Cash on Delivery" in body
    assert "Pending" in body
    assert "New Delhi" in body
    assert "Back to menu" in body
    print("PASS: 14. Order confirmation displays correctly.")


# ---------------------------------------------------------------------------
# 15. Customers cannot view another customer's order.
# ---------------------------------------------------------------------------
def test_customer_cannot_view_another_customers_order():
    client = test_client()
    email1 = f"viewer1{TS}@example.com"
    _register_and_login(client, email1)
    product_id, product_name, product_price = _get_available_product(client)
    _add_product_to_cart(client, product_id)
    client.post("/checkout", data=_checkout_form_data(csrf_token=_csrf(client, "/checkout")),
                follow_redirects=False)

    with app.app_context():
        from app.models import Order
        user1 = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email1).first()
        order = Order.query.filter_by(user_id=user1.id).first()
        order_number = order.order_number

    # Different customer tries to view the order
    client2 = test_client()
    email2 = f"viewer2{TS}@example.com"
    _register_and_login(client2, email2)
    resp = client2.get(f"/orders/{order_number}/confirmation", follow_redirects=False)
    assert resp.status_code in (403, 302), f"Expected 403 or redirect, got {resp.status_code}"
    print("PASS: 15. Customers cannot view another customer's order.")


# ---------------------------------------------------------------------------
# 16. Duplicate order submission is prevented (repeat POST finds empty cart).
# ---------------------------------------------------------------------------
def test_duplicate_submission_prevented():
    client = test_client()
    email = f"dupsubmit{TS}@example.com"
    _register_and_login(client, email)
    product_id, product_name, product_price = _get_available_product(client)
    _add_product_to_cart(client, product_id, quantity=1)

    # First submission succeeds
    resp1 = client.post("/checkout", data=_checkout_form_data(csrf_token=_csrf(client, "/checkout")),
                        follow_redirects=False)
    assert resp1.status_code in (302,), f"First submit expected redirect, got {resp1.status_code}"

    # Cart is now empty; a second submission to /checkout is redirected to cart
    resp2 = client.post("/checkout", data=_checkout_form_data(csrf_token=_csrf(client, "/checkout")),
                        follow_redirects=False)
    assert resp2.status_code in (302,), f"Second submit expected redirect, got {resp2.status_code}"
    assert "/cart" in resp2.headers.get("Location", "")

    with app.app_context():
        from app.models import Order
        user = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email).first()
        orders = Order.query.filter_by(user_id=user.id).all()
        assert len(orders) == 1, f"Expected exactly 1 order, got {len(orders)}"
    print("PASS: 16. Duplicate order submission is prevented.")


# ---------------------------------------------------------------------------
# 17. Admin cannot access customer checkout.
# ---------------------------------------------------------------------------
def test_admin_cannot_access_checkout():
    client = test_client()
    with app.app_context():
        from app.models import User
        from app.extensions import db
        admin = User.query.filter_by(email="checkoutadmin@test.com").first()
        if not admin:
            admin = User(name="Checkout Admin", email="checkoutadmin@test.com", role="admin")
            admin.set_password("adminpass123")
            db.session.add(admin)
            db.session.commit()
    client.post("/login", data={
        "csrf_token": _csrf(client, "/login"),
        "email": "checkoutadmin@test.com",
        "password": "adminpass123",
    }, follow_redirects=False)
    resp = client.get("/checkout", follow_redirects=False)
    assert resp.status_code in (302, 403), f"Expected redirect/403, got {resp.status_code}"
    print("PASS: 17. Admin cannot access customer checkout.")


if __name__ == "__main__":
    tests = [
        test_logged_in_customer_can_access_checkout,
        test_logged_out_visitor_redirected_to_login,
        test_empty_cart_cannot_be_checked_out,
        test_valid_checkout_places_order,
        test_invalid_phone_rejected,
        test_invalid_pin_rejected,
        test_unavailable_product_cannot_be_ordered,
        test_non_vegetarian_product_cannot_be_ordered,
        test_prices_calculated_on_backend,
        test_order_and_items_persist_with_snapshots,
        test_special_instructions_preserved,
        test_cart_cleared_after_successful_order,
        test_order_confirmation_displays_correctly,
        test_customer_cannot_view_another_customers_order,
        test_duplicate_submission_prevented,
        test_admin_cannot_access_checkout,
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
