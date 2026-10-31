import re
import secrets
from urllib.parse import urlparse, urljoin

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, current_user

from app.extensions import db
from app.models import User

auth_bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# CSRF protection (session-based, no extra dependency)
# ---------------------------------------------------------------------------

def _csrf_token():
    """Return a CSRF token, creating one in the session if needed."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def _csrf_valid(token):
    return bool(token) and token == session.get("_csrf_token")


@auth_bp.app_context_processor
def inject_csrf():
    return dict(csrf_token=_csrf_token)


def _is_safe_url(target):
    """Check that a redirect target is relative to this host (no open redirects)."""
    if not target:
        return False
    ref_url = urlparse(urljoin(request.host_url, "/"))
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("main.customer_home"))

    if request.method == "POST":
        # CSRF check.
        if not _csrf_valid(request.form.get("csrf_token")):
            flash("Invalid request. Please try again.", "error")
            return render_template("auth/login.html"), 400

        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        remember = "remember" in request.form

        errors = []
        if not email:
            errors.append("Email address is required.")
        if not password:
            errors.append("Password is required.")

        user = None
        if not errors:
            user = User.query.filter_by(email=email).first()
            if not user or not user.check_password(password):
                errors.append("Invalid email or password.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("auth/login.html")

        login_user(user, remember=remember)
        flash("Welcome back, " + user.name + ".", "success")

        next_page = request.args.get("next") or request.form.get("next")
        if not _is_safe_url(next_page):
            next_page = None

        if user.is_admin:
            return redirect(next_page or url_for("admin.dashboard"))
        return redirect(next_page or url_for("main.customer_home"))

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("main.customer_home"))

    if request.method == "POST":
        # CSRF check.
        if not _csrf_valid(request.form.get("csrf_token")):
            flash("Invalid request. Please try again.", "error")
            return render_template("auth/register.html"), 400

        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        terms = "terms" in request.form

        errors = []

        # Required fields.
        if not name:
            errors.append("Full name is required.")
        if not email:
            errors.append("Email address is required.")
        if not phone:
            errors.append("Phone number is required.")
        if not password:
            errors.append("Password is required.")
        if not confirm_password:
            errors.append("Please confirm your password.")
        if not terms:
            errors.append("You must accept the Terms and Conditions.")

        # Email format.
        if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            errors.append("Please enter a valid email address.")

        # Phone format (digits, spaces, dashes, parentheses, plus; 7–15 chars).
        if phone and not re.match(r"^[\d\s\-()\+]{7,20}$", phone):
            errors.append("Please enter a valid phone number.")

        # Password strength.
        if password and len(password) < 8:
            errors.append("Password must be at least 8 characters.")

        # Password match.
        if password and confirm_password and password != confirm_password:
            errors.append("Password and confirm password do not match.")

        # Unique email.
        if email and User.query.filter_by(email=email).first():
            errors.append("An account with this email already exists.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("auth/register.html")

        # Customers can only register as customers. Admin accounts are created
        # out-of-band via `flask create-admin`. Role is never user-selectable.
        user = User(name=name, email=email, phone=phone, role="customer")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
