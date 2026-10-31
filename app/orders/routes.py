import re
import secrets
from datetime import datetime
from decimal import Decimal
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Cart, CartItem, Order, OrderItem, Product

orders_bp = Blueprint("orders", __name__)


# ---------------------------------------------------------------------------
# CSRF protection (session-based, same pattern as auth and cart blueprints)
# ---------------------------------------------------------------------------

def _csrf_token():
    """Return a CSRF token, creating one in the session if needed."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def _csrf_valid(token):
    return bool(token) and token == session.get("_csrf_token")


# ---------------------------------------------------------------------------
# Role guards
# ---------------------------------------------------------------------------

def customer_required(f):
    """Only authenticated non-admin customers may proceed."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        if current_user.is_admin:
            flash("Admin users cannot access customer checkout.", "warning")
            return redirect(url_for("admin.dashboard"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_order_number():
    """Generate a unique order number like BB-20261031-A1B2C3."""
    today = datetime.utcnow().strftime("%Y%m%d")
    while True:
        number = f"BB-{today}-{secrets.token_hex(3).upper()}"
        if not Order.query.filter_by(order_number=number).first():
            return number


def _validate_indian_phone(phone):
    """Validate an Indian mobile number.

    Accepts 10-digit numbers (starting with 6-9), optionally prefixed with
    +91 or 0. Spaces, dashes and parentheses are ignored.
    """
    if not phone:
        return False
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return len(digits) == 10 and digits[0] in "6789"


def _delivery_fee():
    """Configurable delivery fee, returned as a Decimal."""
    return Decimal(str(current_app.config.get("DELIVERY_FEE", "0.00")))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@orders_bp.route("/checkout", methods=["GET"])
@customer_required
def checkout():
    """Display the checkout page with order summary and delivery form."""
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart or not cart.items:
        flash("Your cart is empty. Add some items before checking out.", "info")
        return redirect(url_for("cart.view_cart"))

    # Guard: every cart item must refer to an available vegetarian product.
    for item in cart.items:
        product = item.product
        if not product:
            flash("Your cart contains an item that is no longer available.", "error")
            return redirect(url_for("cart.view_cart"))
        if not product.is_available:
            flash(f'"{product.name}" is currently unavailable.', "error")
            return redirect(url_for("cart.view_cart"))
        if not product.is_vegetarian:
            flash(f'"{product.name}" is not vegetarian and cannot be ordered.', "error")
            return redirect(url_for("cart.view_cart"))

    subtotal = cart.subtotal
    delivery_fee = _delivery_fee()
    total = subtotal + delivery_fee

    # Pre-fill name and phone from the customer's profile.
    form_defaults = {
        "customer_name": current_user.name or "",
        "phone": current_user.phone or "",
    }

    return render_template(
        "orders/checkout.html",
        cart=cart,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total=total,
        form_defaults=form_defaults,
    )


@orders_bp.route("/checkout", methods=["POST"])
@customer_required
def place_order():
    """Validate the delivery form and place the order in one transaction."""
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart or not cart.items:
        flash("Your cart is empty.", "error")
        return redirect(url_for("cart.view_cart"))

    # Re-validate cart contents against current product data.
    for item in cart.items:
        product = item.product
        if not product or not product.is_available or not product.is_vegetarian:
            flash(
                "Your cart contains an item that is no longer available. "
                "Please review your cart.",
                "error",
            )
            return redirect(url_for("cart.view_cart"))

    # CSRF check.
    if not _csrf_valid(request.form.get("csrf_token")):
        flash("Invalid request. Please try again.", "error")
        return redirect(url_for("orders.checkout"))

    # Prevent duplicate submissions from repeated clicks.
    if session.get("_placing_order"):
        flash("Your order is already being processed. Please wait.", "warning")
        return redirect(url_for("cart.view_cart"))

    # --- Collect and sanitize form data (never trust frontend totals) ---
    customer_name = (request.form.get("customer_name") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    delivery_address = (request.form.get("delivery_address") or "").strip()
    landmark = (request.form.get("landmark") or "").strip() or None
    city = (request.form.get("city") or "").strip()
    state = (request.form.get("state") or "").strip()
    pin_code = (request.form.get("pin_code") or "").strip()
    delivery_instructions = (request.form.get("delivery_instructions") or "").strip() or None

    form_values = {
        "customer_name": customer_name,
        "phone": phone,
        "delivery_address": delivery_address,
        "landmark": landmark or "",
        "city": city,
        "state": state,
        "pin_code": pin_code,
        "delivery_instructions": delivery_instructions or "",
    }

    # --- Server-side validation ---
    errors = []
    if not customer_name:
        errors.append("Full name is required.")
    if not phone:
        errors.append("Phone number is required.")
    elif not _validate_indian_phone(phone):
        errors.append("Please enter a valid Indian phone number (10 digits).")
    if not delivery_address:
        errors.append("Delivery address is required.")
    if not city:
        errors.append("City is required.")
    if not state:
        errors.append("State is required.")
    if not pin_code:
        errors.append("PIN code is required.")
    elif not re.match(r"^\d{6}$", pin_code):
        errors.append("PIN code must be a 6-digit number.")

    if errors:
        for error in errors:
            flash(error, "error")
        subtotal = cart.subtotal
        delivery_fee = _delivery_fee()
        total = subtotal + delivery_fee
        return render_template(
            "orders/checkout.html",
            cart=cart,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            total=total,
            form_defaults=form_values,
        )

    # --- Place the order in a single database transaction ---
    session["_placing_order"] = True
    try:
        subtotal = cart.subtotal
        delivery_fee = _delivery_fee()
        total = subtotal + delivery_fee

        order = Order(
            order_number=_generate_order_number(),
            user_id=current_user.id,
            customer_name=customer_name,
            phone=phone,
            delivery_address=delivery_address,
            landmark=landmark,
            city=city,
            state=state,
            pin_code=pin_code,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            total_amount=total,
            payment_method="cod",
            payment_status="pending",
            order_status="pending",
            delivery_instructions=delivery_instructions,
        )
        db.session.add(order)
        db.session.flush()  # assign order.id before creating items

        order_items = []
        for item in cart.items:
            product = item.product
            order_items.append(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    product_name=product.name,
                    unit_price=product.price,
                    quantity=item.quantity,
                    subtotal=product.price * item.quantity,
                    special_instructions=item.notes,
                )
            )
        db.session.add_all(order_items)

        # Clear the cart only after the order and its items are created.
        CartItem.query.filter_by(cart_id=cart.id).delete()

        db.session.commit()
        flash("Your order has been placed successfully.", "success")
        return redirect(
            url_for("orders.order_confirmation", order_number=order.order_number)
        )
    except Exception:
        db.session.rollback()
        flash(
            "Something went wrong while placing your order. Please try again.",
            "error",
        )
        return redirect(url_for("orders.checkout"))
    finally:
        session.pop("_placing_order", None)


@orders_bp.route("/orders/<order_number>/confirmation", methods=["GET"])
@login_required
def order_confirmation(order_number):
    """Display the order confirmation page.

    Accessible to the customer who placed the order, or to an admin.
    """
    order = Order.query.filter_by(order_number=order_number).first_or_404()

    if not current_user.is_admin and order.user_id != current_user.id:
        abort(403)

    return render_template("orders/confirmation.html", order=order)
