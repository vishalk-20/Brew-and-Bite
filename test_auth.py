"""Comprehensive tests for customer authentication feature."""
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


# ---------------------------------------------------------------------------
# 1. Customer can register successfully.
# ---------------------------------------------------------------------------
def test_customer_register_success():
    client = test_client()
    email = f"regtest{TS}@example.com"
    resp = client.post("/register", data={
        "csrf_token": _csrf(client, "/register"),
        "name": "Reg Test User",
        "email": email,
        "phone": "+1 555-0123",
        "password": "securepass123",
        "confirm_password": "securepass123",
        "terms": "on",
    }, follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}: {resp.get_data(as_text=True)[:200]}"
    assert "/login" in resp.headers.get("Location", ""), f"Expected redirect to login, got {resp.headers.get('Location')}"
    print("PASS: 1. Customer can register successfully.")

# ---------------------------------------------------------------------------
# 2. Duplicate email registration is rejected.
# ---------------------------------------------------------------------------
def test_duplicate_email_rejected():
    client = test_client()
    email = f"duptest{TS}@example.com"
    # Register first
    client.post("/register", data={
        "csrf_token": _csrf(client, "/register"),
        "name": "Dup User",
        "email": email,
        "phone": "+1 555-0123",
        "password": "securepass123",
        "confirm_password": "securepass123",
        "terms": "on",
    }, follow_redirects=False)
    # Try again with same email
    resp = client.post("/register", data={
        "csrf_token": _csrf(client, "/register"),
        "name": "Dup User 2",
        "email": email,
        "phone": "+1 555-0999",
        "password": "securepass123",
        "confirm_password": "securepass123",
        "terms": "on",
    }, follow_redirects=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "already exists" in body.lower(), f"Expected duplicate email error, got: {body[:200]}"
    print("PASS: 2. Duplicate email registration is rejected.")

# ---------------------------------------------------------------------------
# 3. Invalid email is rejected.
# ---------------------------------------------------------------------------
def test_invalid_email_rejected():
    client = test_client()
    resp = client.post("/register", data={
        "csrf_token": _csrf(client, "/register"),
        "name": "Bad Email",
        "email": "not-an-email",
        "phone": "+1 555-0123",
        "password": "securepass123",
        "confirm_password": "securepass123",
        "terms": "on",
    }, follow_redirects=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "valid email" in body.lower(), f"Expected invalid email error, got: {body[:200]}"
    print("PASS: 3. Invalid email is rejected.")

# ---------------------------------------------------------------------------
# 4. Weak password is rejected.
# ---------------------------------------------------------------------------
def test_weak_password_rejected():
    client = test_client()
    resp = client.post("/register", data={
        "csrf_token": _csrf(client, "/register"),
        "name": "Weak Pw",
        "email": f"weakpw{TS}@example.com",
        "phone": "+1 555-0123",
        "password": "short",
        "confirm_password": "short",
        "terms": "on",
    }, follow_redirects=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "8 characters" in body, f"Expected weak password error, got: {body[:200]}"
    print("PASS: 4. Weak password is rejected.")

# ---------------------------------------------------------------------------
# 5. Password mismatch is rejected.
# ---------------------------------------------------------------------------
def test_password_mismatch_rejected():
    client = test_client()
    resp = client.post("/register", data={
        "csrf_token": _csrf(client, "/register"),
        "name": "Mismatch",
        "email": f"mismatch{TS}@example.com",
        "phone": "+1 555-0123",
        "password": "securepass123",
        "confirm_password": "differentpass",
        "terms": "on",
    }, follow_redirects=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "do not match" in body.lower(), f"Expected password mismatch error, got: {body[:200]}"
    print("PASS: 5. Password mismatch is rejected.")

# ---------------------------------------------------------------------------
# 6. Customer password is stored as a hash.
# ---------------------------------------------------------------------------
def test_password_stored_as_hash():
    client = test_client()
    email = f"hashtest{TS}@example.com"
    client.post("/register", data={
        "csrf_token": _csrf(client, "/register"),
        "name": "Hash Test",
        "email": email,
        "phone": "+1 555-0123",
        "password": "securepass123",
        "confirm_password": "securepass123",
        "terms": "on",
    }, follow_redirects=False)
    with app.app_context():
        from app.models import User
        user = User.query.filter_by(email=email).first()
        assert user is not None, "User should exist"
        assert user.password_hash != "securepass123", "Password should be hashed, not plaintext"
        assert len(user.password_hash) > 20, f"Expected a hash, got: {user.password_hash}"
        assert user.role == "customer", f"Expected role=customer, got {user.role}"
        assert user.phone == "+1 555-0123", f"Expected phone to be saved, got {user.phone}"
    print("PASS: 6. Customer password is stored as a hash.")

# ---------------------------------------------------------------------------
# 7. Customer can log in.
# ---------------------------------------------------------------------------
def test_customer_can_login():
    client = test_client()
    email = f"logintest{TS}@example.com"
    # Register first
    client.post("/register", data={
        "csrf_token": _csrf(client, "/register"),
        "name": "Login Test",
        "email": email,
        "phone": "+1 555-0123",
        "password": "securepass123",
        "confirm_password": "securepass123",
        "terms": "on",
    }, follow_redirects=False)
    # Now login
    resp = client.post("/login", data={
        "csrf_token": _csrf(client, "/login"),
        "email": email,
        "password": "securepass123",
    }, follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    assert "/customer" in resp.headers.get("Location", ""), f"Expected redirect to customer home, got {resp.headers.get('Location')}"
    print("PASS: 7. Customer can log in.")

# ---------------------------------------------------------------------------
# 8. Incorrect credentials are rejected.
# ---------------------------------------------------------------------------
def test_incorrect_credentials_rejected():
    client = test_client()
    resp = client.post("/login", data={
        "csrf_token": _csrf(client, "/login"),
        "email": "nonexistent@example.com",
        "password": "wrongpassword",
    }, follow_redirects=False)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "invalid" in body.lower(), f"Expected invalid credentials error, got: {body[:200]}"
    print("PASS: 8. Incorrect credentials are rejected.")

# ---------------------------------------------------------------------------
# 9. Customer can log out.
# ---------------------------------------------------------------------------
def test_customer_can_logout():
    client = test_client()
    email = f"logouttest{TS}@example.com"
    client.post("/register", data={
        "csrf_token": _csrf(client, "/register"),
        "name": "Logout Test",
        "email": email,
        "phone": "+1 555-0123",
        "password": "securepass123",
        "confirm_password": "securepass123",
        "terms": "on",
    }, follow_redirects=False)
    client.post("/login", data={
        "csrf_token": _csrf(client, "/login"),
        "email": email,
        "password": "securepass123",
    }, follow_redirects=False)
    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    print("PASS: 9. Customer can log out.")

# ---------------------------------------------------------------------------
# 10. Admin login still works.
# 11. Admin is redirected to the admin dashboard.
# ---------------------------------------------------------------------------
def test_admin_login_and_dashboard_redirect():
    client = test_client()
    with app.app_context():
        from app.models import User
        from app.extensions import db
        admin = User.query.filter_by(email="admintest@test.com").first()
        if not admin:
            admin = User(name="Test Admin", email="admintest@test.com", role="admin")
            admin.set_password("adminpass123")
            db.session.add(admin)
            db.session.commit()

    resp = client.post("/login", data={
        "csrf_token": _csrf(client, "/login"),
        "email": "admintest@test.com",
        "password": "adminpass123",
    }, follow_redirects=False)
    assert resp.status_code in (302,), f"Expected redirect, got {resp.status_code}"
    assert "/admin" in resp.headers.get("Location", ""), f"Expected redirect to admin, got {resp.headers.get('Location')}"
    print("PASS: 10. Admin login still works.")
    print("PASS: 11. Admin is redirected to the admin dashboard.")

# ---------------------------------------------------------------------------
# 12. Customers cannot access admin routes.
# ---------------------------------------------------------------------------
def test_customer_cannot_access_admin_routes():
    client = test_client()
    email = f"custadmin{TS}@example.com"
    client.post("/register", data={
        "csrf_token": _csrf(client, "/register"),
        "name": "Cust Admin Test",
        "email": email,
        "phone": "+1 555-0123",
        "password": "securepass123",
        "confirm_password": "securepass123",
        "terms": "on",
    }, follow_redirects=False)
    client.post("/login", data={
        "csrf_token": _csrf(client, "/login"),
        "email": email,
        "password": "securepass123",
    }, follow_redirects=False)
    resp = client.get("/admin/", follow_redirects=False)
    assert resp.status_code in (302, 403), f"Expected 302 or 403, got {resp.status_code}"
    print("PASS: 12. Customers cannot access admin routes.")

# ---------------------------------------------------------------------------
# 13. Navigation changes according to authentication status.
# ---------------------------------------------------------------------------
def test_navigation_changes():
    client = test_client()
    # Logged out
    resp = client.get("/login")
    body = resp.get_data(as_text=True)
    assert 'href="/login"' in body, "Logged-out nav should show Login"
    assert 'href="/register"' in body, "Logged-out nav should show Sign Up"
    assert "Logout" not in body, "Logged-out nav should not show Logout"
    assert "Admin Dashboard" not in body, "Logged-out nav should not show Admin Dashboard"
    print("PASS: 13a. Navigation shows Login/Sign Up when logged out.")

    # Logged in as customer
    email = f"navcust{TS}@example.com"
    client.post("/register", data={
        "csrf_token": _csrf(client, "/register"),
        "name": "Nav Cust",
        "email": email,
        "phone": "+1 555-0123",
        "password": "securepass123",
        "confirm_password": "securepass123",
        "terms": "on",
    }, follow_redirects=False)
    client.post("/login", data={
        "csrf_token": _csrf(client, "/login"),
        "email": email,
        "password": "securepass123",
    }, follow_redirects=False)
    resp = client.get("/customer")
    body = resp.get_data(as_text=True)
    assert "Logout" in body, "Customer nav should show Logout"
    assert "My Account" in body, "Customer nav should show My Account"
    assert 'href="/login"' not in body, "Customer nav should not show Login"
    assert 'href="/register"' not in body, "Customer nav should not show Sign Up"
    print("PASS: 13b. Navigation shows My Account/Logout when customer logged in.")

    # Logged in as admin
    client2 = test_client()
    with app.app_context():
        from app.models import User
        from app.extensions import db
        admin = User.query.filter_by(email="navadmin@test.com").first()
        if not admin:
            admin = User(name="Nav Admin", email="navadmin@test.com", role="admin")
            admin.set_password("adminpass123")
            db.session.add(admin)
            db.session.commit()

    client2.post("/login", data={
        "csrf_token": _csrf(client2, "/login"),
        "email": "navadmin@test.com",
        "password": "adminpass123",
    }, follow_redirects=False)
    resp = client2.get("/admin/")
    body = resp.get_data(as_text=True)
    assert "Logout" in body, "Admin nav should show Logout"
    print("PASS: 13c. Navigation shows Admin Dashboard/Logout when admin logged in.")

# ---------------------------------------------------------------------------
# 14. Existing admin functionality remains unaffected.
# ---------------------------------------------------------------------------
def test_admin_functionality_unaffected():
    client = test_client()
    with app.app_context():
        from app.models import User
        from app.extensions import db
        admin = User.query.filter_by(email="funcadmin@test.com").first()
        if not admin:
            admin = User(name="Func Admin", email="funcadmin@test.com", role="admin")
            admin.set_password("adminpass123")
            db.session.add(admin)
            db.session.commit()

    client.post("/login", data={
        "csrf_token": _csrf(client, "/login"),
        "email": "funcadmin@test.com",
        "password": "adminpass123",
    }, follow_redirects=False)
    resp = client.get("/admin/")
    assert resp.status_code == 200, f"Admin dashboard should be 200, got {resp.status_code}"
    resp = client.get("/admin/menu")
    assert resp.status_code == 200, f"Admin menu list should be 200, got {resp.status_code}"
    print("PASS: 14. Existing admin functionality remains unaffected.")


if __name__ == "__main__":
    tests = [
        test_customer_register_success,
        test_duplicate_email_rejected,
        test_invalid_email_rejected,
        test_weak_password_rejected,
        test_password_mismatch_rejected,
        test_password_stored_as_hash,
        test_customer_can_login,
        test_incorrect_credentials_rejected,
        test_customer_can_logout,
        test_admin_login_and_dashboard_redirect,
        test_customer_cannot_access_admin_routes,
        test_navigation_changes,
        test_admin_functionality_unaffected,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {len(tests)} tests.")
