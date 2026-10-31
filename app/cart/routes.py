import secrets

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Cart, CartItem, Product

cart_bp = Blueprint("cart", __name__, url_prefix="/cart")


def _csrf_token():
    """Return a CSRF token, creating one in the session if needed."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def _csrf_valid(token):
    return bool(token) and token == session.get("_csrf_token")


def _get_or_create_cart(user_id):
    """Fetch the customer's cart, creating it on first use."""
    cart = Cart.query.filter_by(user_id=user_id).first()
    if not cart:
        cart = Cart(user_id=user_id)
        db.session.add(cart)
        db.session.commit()
    return cart


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@cart_bp.route("/", methods=["GET"], strict_slashes=False)
@login_required
def view_cart():
    """Display the current customer's cart."""
    if current_user.is_admin:
        flash("Admin users cannot access the customer cart.", "warning")
        return redirect(url_for("admin.dashboard"))

    # Process a pending add-to-cart that was deferred before login.
    pending_product_id = session.pop("pending_add_product_id", None)
    if pending_product_id:
        product = Product.query.get(pending_product_id)
        if product and product.is_vegetarian and product.is_available:
            cart = _get_or_create_cart(current_user.id)
            existing = CartItem.query.filter_by(
                cart_id=cart.id, product_id=product.id
            ).first()
            if existing:
                existing.quantity += 1
            else:
                db.session.add(
                    CartItem(cart_id=cart.id, product_id=product.id, quantity=1)
                )
            db.session.commit()
            flash(f'"{product.name}" added to your cart.', "success")
        elif product:
            flash(
                f'"{product.name}" cannot be added to your cart at this time.',
                "warning",
            )

    cart = _get_or_create_cart(current_user.id)

    # Flag any line items whose product is no longer available.
    unavailable_items = [
        item for item in cart.items if not item.product.is_available
    ]

    return render_template(
        "cart/cart.html",
        cart=cart,
        unavailable_items=unavailable_items,
    )


@cart_bp.route("/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    """Add a product to the customer's cart (increase quantity if already present)."""
    if not current_user.is_authenticated:
        # Preserve intent: after login we will add this product automatically.
        session["pending_add_product_id"] = product_id
        flash("Please log in to add items to your cart.", "warning")
        return redirect(url_for("auth.login", next=url_for("cart.view_cart")))

    if current_user.is_admin:
        flash("Admin users cannot add items to the cart.", "warning")
        return redirect(url_for("admin.dashboard"))

    # CSRF check.
    if not _csrf_valid(request.form.get("csrf_token")):
        flash("Invalid request. Please try again.", "error")
        return redirect(url_for("main.menu"))

    # Validate product exists, is vegetarian and is available.
    product = Product.query.get(product_id)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("main.menu"))

    if not product.is_vegetarian:
        flash("Only vegetarian items can be added to the cart.", "error")
        return redirect(url_for("main.menu"))

    if not product.is_available:
        flash(f'"{product.name}" is currently unavailable.', "error")
        return redirect(url_for("main.menu"))

    cart = _get_or_create_cart(current_user.id)

    existing_item = CartItem.query.filter_by(
        cart_id=cart.id, product_id=product.id
    ).first()
    quantity = request.form.get("quantity", type=int) or 1
    if quantity < 1:
        quantity = 1
    notes = (request.form.get("notes") or "").strip() or None

    if existing_item:
        existing_item.quantity += quantity
        if notes and not existing_item.notes:
            existing_item.notes = notes
        db.session.commit()
        flash(f'Another "{product.name}" added to your cart.', "success")
    else:
        db.session.add(
            CartItem(cart_id=cart.id, product_id=product.id, quantity=quantity, notes=notes)
        )
        db.session.commit()
        flash(f'"{product.name}" added to your cart.', "success")

    next_page = request.form.get("next") or request.args.get("next")
    if next_page:
        return redirect(next_page)
    return redirect(url_for("cart.view_cart"))


@cart_bp.route("/update/<int:item_id>", methods=["POST"])
@login_required
def update_quantity(item_id):
    """Update the quantity of a cart item (must stay >= 1)."""
    if current_user.is_admin:
        flash("Admin users cannot modify the cart.", "warning")
        return redirect(url_for("admin.dashboard"))

    if not _csrf_valid(request.form.get("csrf_token")):
        flash("Invalid request. Please try again.", "error")
        return redirect(url_for("cart.view_cart"))

    item = CartItem.query.get_or_404(item_id)

    # Validate ownership — customers cannot touch another customer's cart.
    if item.cart.user_id != current_user.id:
        flash("You cannot modify another customer's cart.", "error")
        return redirect(url_for("cart.view_cart"))

    # If the product is no longer available, remove it instead.
    if not item.product.is_available:
        product_name = item.product.name
        db.session.delete(item)
        db.session.commit()
        flash(
            f'"{product_name}" is no longer available and was removed from your cart.',
            "warning",
        )
        return redirect(url_for("cart.view_cart"))

    quantity = request.form.get("quantity", type=int)
    if not quantity or quantity < 1:
        flash("Quantity must be at least 1.", "error")
        return redirect(url_for("cart.view_cart"))

    item.quantity = quantity
    db.session.commit()
    flash(f'Quantity updated for "{item.product.name}".', "success")
    return redirect(url_for("cart.view_cart"))


@cart_bp.route("/remove/<int:item_id>", methods=["POST"])
@login_required
def remove_item(item_id):
    """Remove a product completely from the customer's cart."""
    if current_user.is_admin:
        flash("Admin users cannot modify the cart.", "warning")
        return redirect(url_for("admin.dashboard"))

    if not _csrf_valid(request.form.get("csrf_token")):
        flash("Invalid request. Please try again.", "error")
        return redirect(url_for("cart.view_cart"))

    item = CartItem.query.get_or_404(item_id)

    # Validate ownership.
    if item.cart.user_id != current_user.id:
        flash("You cannot modify another customer's cart.", "error")
        return redirect(url_for("cart.view_cart"))

    product_name = item.product.name
    db.session.delete(item)
    db.session.commit()
    flash(f'"{product_name}" removed from your cart.', "success")
    return redirect(url_for("cart.view_cart"))
