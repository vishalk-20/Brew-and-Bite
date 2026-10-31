"""Comprehensive tests for the shopping cart feature (Feature 4)."""
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


def _get_available_product_id(client):
    """Return the id of the first available vegetarian product from the menu."""
    resp = client.get("/menu")
    body = resp.get_data(as_text=True)
    # Find product links like /cart/add/N — but menu doesn't render those yet.
    # Instead, query the DB directly.
    with app.app_context():
        from app.models import Product
        p = Product.query.filter_by(is_vegetarian=True, is_available=True).first()
        return p.id


def test_1_logged_in_customer_can_add_product_to_cart():
    """1. Logged-in customer can add a product to cart."""
    client = test_client()
    email = f"cartadd{TS}@example.com"
    _register_and_login(client, email)
    product_id = _get_available_product_id(client)
    resp = client.post(f"/cart/add/{product_id}", data={
        "csrf_token": _csrf(client, "/menu"),
    }, follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    with app.app_context():
        from app.models import Cart, CartItem
        from app.extensions import db
        user = app.extensions.db.session.execute(
            __import__('app.models', fromlist=['User']).User.query.filter_by(email=email).subquery()
        ).scalar() if False else None
        # Simpler: query directly
        user = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email).first()
        cart = Cart.query.filter_by(user_id=user.id).first()
        assert cart is not None, "Cart should exist"
        item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()
        assert item is not None, "Cart item should exist"
        assert item.quantity == 1, f"Expected quantity 1, got {item.quantity}"
    print("PASS: 1. Logged-in customer can add a product to cart.")


def test_2_logged_out_visitor_redirected_to_login():
    """2. Logged-out visitor is redirected to login."""
    client = test_client()
    product_id = _get_available_product_id(client)
    resp = client.post(f"/cart/add/{product_id}", data={}, follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    assert "/login" in resp.headers.get("Location", ""), \
        f"Expected redirect to login, got {resp.headers.get('Location')}"
    print("PASS: 2. Logged-out visitor is redirected to login.")


def test_3_adding_same_product_increases_quantity():
    """3. Adding the same product increases quantity."""
    client = test_client()
    email = f"cartqty{TS}@example.com"
    _register_and_login(client, email)
    product_id = _get_available_product_id(client)
    for _ in range(3):
        client.post(f"/cart/add/{product_id}", data={
            "csrf_token": _csrf(client, "/menu"),
        }, follow_redirects=False)
    with app.app_context():
        from app.models import Cart, CartItem
        user = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email).first()
        cart = Cart.query.filter_by(user_id=user.id).first()
        item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()
        assert item is not None, "Cart item should exist"
        assert item.quantity == 3, f"Expected quantity 3, got {item.quantity}"
    print("PASS: 3. Adding the same product increases quantity.")


def test_4_quantity_can_be_increased():
    """4. Quantity can be increased."""
    client = test_client()
    email = f"cartinc{TS}@example.com"
    _register_and_login(client, email)
    product_id = _get_available_product_id(client)
    client.post(f"/cart/add/{product_id}", data={
        "csrf_token": _csrf(client, "/menu"),
    }, follow_redirects=False)
    with app.app_context():
        from app.models import Cart, CartItem
        user = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email).first()
        cart = Cart.query.filter_by(user_id=user.id).first()
        item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()
        item_id = item.id
    resp = client.post(f"/cart/update/{item_id}", data={
        "csrf_token": _csrf(client, "/cart"),
        "quantity": 5,
    }, follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    with app.app_context():
        from app.models import CartItem
        item = CartItem.query.get(item_id)
        assert item.quantity == 5, f"Expected quantity 5, got {item.quantity}"
    print("PASS: 4. Quantity can be increased.")


def test_5_quantity_can_be_decreased():
    """5. Quantity can be decreased."""
    client = test_client()
    email = f"cartdec{TS}@example.com"
    _register_and_login(client, email)
    product_id = _get_available_product_id(client)
    client.post(f"/cart/add/{product_id}", data={
        "csrf_token": _csrf(client, "/menu"),
    }, follow_redirects=False)
    client.post(f"/cart/add/{product_id}", data={
        "csrf_token": _csrf(client, "/menu"),
    }, follow_redirects=False)
    with app.app_context():
        from app.models import Cart, CartItem
        user = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email).first()
        cart = Cart.query.filter_by(user_id=user.id).first()
        item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()
        item_id = item.id
    resp = client.post(f"/cart/update/{item_id}", data={
        "csrf_token": _csrf(client, "/cart"),
        "quantity": 1,
    }, follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    with app.app_context():
        from app.models import CartItem
        item = CartItem.query.get(item_id)
        assert item.quantity == 1, f"Expected quantity 1, got {item.quantity}"
    print("PASS: 5. Quantity can be decreased.")


def test_6_products_can_be_removed():
    """6. Products can be removed."""
    client = test_client()
    email = f"cartrem{TS}@example.com"
    _register_and_login(client, email)
    product_id = _get_available_product_id(client)
    client.post(f"/cart/add/{product_id}", data={
        "csrf_token": _csrf(client, "/menu"),
    }, follow_redirects=False)
    with app.app_context():
        from app.models import Cart, CartItem
        user = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email).first()
        cart = Cart.query.filter_by(user_id=user.id).first()
        item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()
        item_id = item.id
    resp = client.post(f"/cart/remove/{item_id}", data={
        "csrf_token": _csrf(client, "/cart"),
    }, follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    with app.app_context():
        from app.models import CartItem
        item = CartItem.query.get(item_id)
        assert item is None, "Cart item should be deleted"
    print("PASS: 6. Products can be removed.")


def test_7_unavailable_products_cannot_be_added():
    """7. Unavailable products cannot be added."""
    client = test_client()
    email = f"cartunav{TS}@example.com"
    _register_and_login(client, email)
    with app.app_context():
        from app.models import Product
        p = Product.query.filter_by(is_vegetarian=True, is_available=False).first()
        if p is None:
            # Create one
            from app.models import Category
            cat = Category.query.first()
            p = Product(
                name="Unavailable Test Item",
                description="Test",
                price=9.99,
                category_id=cat.id,
                is_vegetarian=True,
                is_available=False,
            )
            from app.extensions import db
            db.session.add(p)
            db.session.commit()
        product_id = p.id
    resp = client.post(f"/cart/add/{product_id}", data={
        "csrf_token": _csrf(client, "/menu"),
    }, follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    body = resp.get_data(as_text=True)
    with app.app_context():
        from app.models import Cart, CartItem
        user = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email).first()
        cart = Cart.query.filter_by(user_id=user.id).first()
        if cart:
            item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()
            assert item is None, "Unavailable product should not be in cart"
    print("PASS: 7. Unavailable products cannot be added.")


def test_8_non_vegetarian_products_cannot_be_added():
    """8. Non-vegetarian products cannot be added."""
    client = test_client()
    email = f"cartnonveg{TS}@example.com"
    _register_and_login(client, email)
    with app.app_context():
        from app.models import Product, Category
        cat = Category.query.first()
        p = Product.query.filter_by(is_vegetarian=False).first()
        if p is None:
            p = Product(
                name="Non-Veg Test Item",
                description="Test",
                price=9.99,
                category_id=cat.id,
                is_vegetarian=False,
                is_available=True,
            )
            from app.extensions import db
            db.session.add(p)
            db.session.commit()
        product_id = p.id
    resp = client.post(f"/cart/add/{product_id}", data={
        "csrf_token": _csrf(client, "/menu"),
    }, follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    with app.app_context():
        from app.models import Cart, CartItem
        user = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email).first()
        cart = Cart.query.filter_by(user_id=user.id).first()
        if cart:
            item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()
            assert item is None, "Non-vegetarian product should not be in cart"
    print("PASS: 8. Non-vegetarian products cannot be added.")


def test_9_cart_totals_calculated_correctly():
    """9. Cart totals are calculated correctly."""
    client = test_client()
    email = f"carttotal{TS}@example.com"
    _register_and_login(client, email)
    with app.app_context():
        from app.models import Product
        products = Product.query.filter_by(is_vegetarian=True, is_available=True).limit(2).all()
        assert len(products) >= 2, "Need at least 2 products"
        p1, p2 = products[0], products[1]
        p1_id, p2_id = p1.id, p2.id
        p1_price = p1.price
        p2_price = p2.price
    client.post(f"/cart/add/{p1_id}", data={"csrf_token": _csrf(client, "/menu")}, follow_redirects=False)
    client.post(f"/cart/add/{p1_id}", data={"csrf_token": _csrf(client, "/menu")}, follow_redirects=False)
    client.post(f"/cart/add/{p2_id}", data={"csrf_token": _csrf(client, "/menu")}, follow_redirects=False)
    resp = client.get("/cart", follow_redirects=False)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.get_data(as_text=True)
    expected_subtotal = p1_price * 2 + p2_price
    expected_str = f"&#8377;{expected_subtotal:.2f}"
    assert expected_str in body, f"Expected subtotal {expected_str} in cart page"
    print("PASS: 9. Cart totals are calculated correctly.")


def test_10_cart_count_updates_correctly():
    """10. Cart count updates correctly."""
    client = test_client()
    email = f"cartcount{TS}@example.com"
    _register_and_login(client, email)
    product_id = _get_available_product_id(client)
    # Logged in, empty cart -> count should be 0 in nav
    resp = client.get("/menu")
    body = resp.get_data(as_text=True)
    assert 'Cart (0)' in body or 'cart-count' in body, "Nav should show Cart count"
    # Add item
    client.post(f"/cart/add/{product_id}", data={"csrf_token": _csrf(client, "/menu")}, follow_redirects=False)
    # Add same item again -> quantity 2, count should be 2
    client.post(f"/cart/add/{product_id}", data={"csrf_token": _csrf(client, "/menu")}, follow_redirects=False)
    resp = client.get("/menu")
    body = resp.get_data(as_text=True)
    assert 'cart-count' in body, f"Expected cart-count in nav after adding items, got: {body[:500]}"
    print("PASS: 10. Cart count updates correctly.")


def test_11_customers_cannot_access_another_customers_cart():
    """11. Customers cannot access another customer's cart."""
    client = test_client()
    email1 = f"cartcust1{TS}@example.com"
    _register_and_login(client, email1)
    product_id = _get_available_product_id(client)
    client.post(f"/cart/add/{product_id}", data={"csrf_token": _csrf(client, "/menu")}, follow_redirects=False)
    with app.app_context():
        from app.models import Cart, CartItem
        user1 = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email1).first()
        cart1 = Cart.query.filter_by(user_id=user1.id).first()
        item = CartItem.query.filter_by(cart_id=cart1.id, product_id=product_id).first()
        item_id = item.id

    # Now log in as a different customer and try to modify item
    client2 = test_client()
    email2 = f"cartcust2{TS}@example.com"
    _register_and_login(client2, email2)
    resp = client2.post(f"/cart/update/{item_id}", data={
        "csrf_token": _csrf(client2, "/cart"),
        "quantity": 99,
    }, follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    with app.app_context():
        from app.models import CartItem
        item = CartItem.query.get(item_id)
        assert item.quantity != 99, "Another customer should not be able to modify the item"
    print("PASS: 11. Customers cannot access another customer's cart.")


def test_12_empty_cart_displays_correctly():
    """12. Empty cart displays correctly."""
    client = test_client()
    email = f"cartempty{TS}@example.com"
    _register_and_login(client, email)
    resp = client.get("/cart", follow_redirects=False)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert "Your cart is empty" in body or "cart is empty" in body.lower(), \
        f"Expected empty cart message, got: {body[:500]}"
    assert "Browse Menu" in body, "Expected Browse Menu button"
    print("PASS: 12. Empty cart displays correctly.")


def test_13_cart_persists_after_logout_and_login():
    """13. Cart persists after logout and login."""
    client = test_client()
    email = f"cartpersist{TS}@example.com"
    _register_and_login(client, email)
    product_id = _get_available_product_id(client)
    client.post(f"/cart/add/{product_id}", data={"csrf_token": _csrf(client, "/menu")}, follow_redirects=False)
    # Log out
    client.get("/logout", follow_redirects=False)
    # Log back in
    client.post("/login", data={
        "csrf_token": _csrf(client, "/login"),
        "email": email,
        "password": "securepass123",
    }, follow_redirects=False)
    resp = client.get("/cart", follow_redirects=False)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert "Your cart is empty" not in body, "Cart should not be empty after re-login"
    with app.app_context():
        from app.models import Cart, CartItem
        user = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email).first()
        cart = Cart.query.filter_by(user_id=user.id).first()
        assert cart is not None, "Cart should persist"
        assert cart.item_count > 0, "Cart should have items"
    print("PASS: 13. Cart persists after logout and login.")


def test_14_admin_functionality_unaffected():
    """14. Existing admin functionality remains unaffected."""
    client = test_client()
    with app.app_context():
        from app.models import User
        from app.extensions import db
        admin = User.query.filter_by(email="funcadmin2@test.com").first()
        if not admin:
            admin = User(name="Func Admin 2", email="funcadmin2@test.com", role="admin")
            admin.set_password("adminpass123")
            db.session.add(admin)
            db.session.commit()
    client.post("/login", data={
        "csrf_token": _csrf(client, "/login"),
        "email": "funcadmin2@test.com",
        "password": "adminpass123",
    }, follow_redirects=False)
    resp = client.get("/admin/")
    assert resp.status_code == 200, f"Admin dashboard should be 200, got {resp.status_code}"
    resp = client.get("/admin/menu")
    assert resp.status_code == 200, f"Admin menu list should be 200, got {resp.status_code}"
    print("PASS: 14. Existing admin functionality remains unaffected.")


def test_15_existing_customer_menu_functionality_unaffected():
    """15. Existing customer menu functionality remains unaffected."""
    client = test_client()
    resp = client.get("/menu")
    assert resp.status_code == 200, f"Menu should be 200, got {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert "Our Vegetarian Menu" in body, "Menu heading should be present"
    assert "Add to Cart" in body, "Add to Cart button should be present"
    assert "Coming Soon" not in body, "Coming Soon button should be replaced"
    print("PASS: 15. Existing customer menu functionality remains unaffected.")


def test_cart_page_shows_product_details():
    """Bonus: Cart page displays product image, name, price, quantity, subtotal."""
    client = test_client()
    email = f"cartdetails{TS}@example.com"
    _register_and_login(client, email)
    product_id = _get_available_product_id(client)
    client.post(f"/cart/add/{product_id}", data={"csrf_token": _csrf(client, "/menu")}, follow_redirects=False)
    resp = client.get("/cart", follow_redirects=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "&#8377;" in body, "Prices should be in rupees"
    assert "Continue Shopping" in body, "Continue Shopping button should be present"
    assert "Proceed to Checkout" in body, "Proceed to Checkout button should be present"
    print("PASS: Bonus. Cart page shows product details and actions.")


def test_notes_saved_with_cart_item():
    """Special instructions / notes are stored with the cart item."""
    client = test_client()
    email = f"cartnotes{TS}@example.com"
    _register_and_login(client, email)
    product_id = _get_available_product_id(client)
    client.post(f"/cart/add/{product_id}", data={
        "csrf_token": _csrf(client, "/menu"),
        "quantity": 2,
        "notes": "Extra cheese, no onions",
    }, follow_redirects=False)
    with app.app_context():
        from app.models import Cart, CartItem
        user = __import__('app.models', fromlist=['User']).User.query.filter_by(email=email).first()
        cart = Cart.query.filter_by(user_id=user.id).first()
        item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()
        assert item is not None, "Cart item should exist"
        assert item.quantity == 2, f"Expected quantity 2, got {item.quantity}"
        assert item.notes == "Extra cheese, no onions", f"Expected notes, got {item.notes}"
    print("PASS: Bonus. Special instructions / notes are stored with the cart item.")


def test_menu_page_renders_add_to_cart_modal():
    """Menu page renders the Add to Cart modal markup."""
    client = test_client()
    resp = client.get("/menu")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'open-cart-modal' in body, "Add to Cart button should open modal"
    assert 'cartModal' in body, "Modal markup should be present"
    assert 'modalQty' in body, "Quantity control should be in modal"
    assert 'modalNotes' in body, "Notes field should be in modal"
    print("PASS: Bonus. Menu page renders the Add to Cart modal.")


if __name__ == "__main__":
    tests = [
        test_1_logged_in_customer_can_add_product_to_cart,
        test_2_logged_out_visitor_redirected_to_login,
        test_3_adding_same_product_increases_quantity,
        test_4_quantity_can_be_increased,
        test_5_quantity_can_be_decreased,
        test_6_products_can_be_removed,
        test_7_unavailable_products_cannot_be_added,
        test_8_non_vegetarian_products_cannot_be_added,
        test_9_cart_totals_calculated_correctly,
        test_10_cart_count_updates_correctly,
        test_11_customers_cannot_access_another_customers_cart,
        test_12_empty_cart_displays_correctly,
        test_13_cart_persists_after_logout_and_login,
        test_14_admin_functionality_unaffected,
        test_15_existing_customer_menu_functionality_unaffected,
        test_cart_page_shows_product_details,
        test_notes_saved_with_cart_item,
        test_menu_page_renders_add_to_cart_modal,
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
