"""Tests for production configuration and error handling (Feature 8).

Covers: SECRET_KEY fallback/fail-fast, SESSION_COOKIE_SECURE defaults,
debug-mode defaults, and custom 404/500 error pages that never expose
stack traces or sensitive details.
"""
import os

from app import create_app


def _set_env(**kwargs):
    """Set env vars, returning previous values so they can be restored."""
    previous = {}
    for key, value in kwargs.items():
        previous[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    return previous


def _restore_env(previous):
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_404_page_renders_without_stack_trace():
    """A missing page shows a friendly 404 with no stack trace."""
    previous = _set_env(APP_ENV="development", SECRET_KEY=None)
    try:
        app = create_app()
    finally:
        _restore_env(previous)
    client = app.test_client()
    resp = client.get("/nonexistent-page-that-does-not-exist", follow_redirects=False)
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert "Page not found" in body, f"Expected friendly 404 message, got: {body[:300]}"
    assert "Traceback" not in body, "404 page must not expose a stack trace"
    print("PASS: 404 page renders with a friendly message and no stack trace.")


def test_500_page_renders_without_stack_trace():
    """A server error shows a friendly 500 with no stack trace."""
    previous = _set_env(APP_ENV="development", SECRET_KEY=None)
    try:
        app = create_app()
    finally:
        _restore_env(previous)

    @app.route("/__test_500__")
    def _raise():
        raise RuntimeError("test boom")

    client = app.test_client()
    resp = client.get("/__test_500__", follow_redirects=False)
    assert resp.status_code == 500, f"Expected 500, got {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert "Something went wrong" in body, f"Expected friendly 500 message, got: {body[:300]}"
    assert "Traceback" not in body, "500 page must not expose a stack trace"
    print("PASS: 500 page renders with a friendly message and no stack trace.")


def test_secret_key_falls_back_to_random_in_dev():
    """Development starts without SECRET_KEY using a random fallback."""
    previous = _set_env(APP_ENV="development", SECRET_KEY=None)
    try:
        app = create_app()
    finally:
        _restore_env(previous)
    secret = app.config.get("SECRET_KEY")
    assert secret, "Dev should fall back to a random SECRET_KEY"
    print("PASS: SECRET_KEY falls back to a random value in development.")


def test_secret_key_required_in_production():
    """Production must fail fast when SECRET_KEY is missing."""
    previous = _set_env(APP_ENV="production", SECRET_KEY=None)
    try:
        try:
            create_app()
        except RuntimeError as exc:
            assert "SECRET_KEY" in str(exc), f"Unexpected message: {exc}"
        else:
            raise AssertionError("Expected RuntimeError for missing SECRET_KEY in production")
    finally:
        _restore_env(previous)
    print("PASS: Missing SECRET_KEY fails fast in production.")


def test_session_cookie_secure_defaults_off_in_dev():
    """Local development over HTTP keeps secure cookies off."""
    previous = _set_env(
        APP_ENV="development", SECRET_KEY="test-secret", SESSION_COOKIE_SECURE=None
    )
    try:
        app = create_app()
    finally:
        _restore_env(previous)
    assert app.config.get("SESSION_COOKIE_SECURE") is False
    print("PASS: SESSION_COOKIE_SECURE defaults off in development.")


def test_session_cookie_secure_defaults_on_in_production():
    """Production over HTTPS defaults secure cookies on."""
    previous = _set_env(
        APP_ENV="production", SECRET_KEY="test-secret", SESSION_COOKIE_SECURE=None
    )
    try:
        app = create_app()
    finally:
        _restore_env(previous)
    assert app.config.get("SESSION_COOKIE_SECURE") is True
    print("PASS: SESSION_COOKIE_SECURE defaults on in production.")


if __name__ == "__main__":
    tests = [
        test_404_page_renders_without_stack_trace,
        test_500_page_renders_without_stack_trace,
        test_secret_key_falls_back_to_random_in_dev,
        test_secret_key_required_in_production,
        test_session_cookie_secure_defaults_off_in_dev,
        test_session_cookie_secure_defaults_on_in_production,
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
