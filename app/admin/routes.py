import os
import secrets
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Category, Order, OrderItem, Product

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _csrf_token():
    """Return a CSRF token, creating one in the session if needed."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def _csrf_valid(token):
    return bool(token) and token == session.get("_csrf_token")


def admin_required(f):
    """Role-based guard: only users with role == 'admin' may proceed."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in as admin to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    total_items = Product.query.count()
    available_items = Product.query.filter_by(is_available=True).count()
    unavailable_items = Product.query.filter_by(is_available=False).count()
    total_categories = Category.query.count()

    total_orders = Order.query.count()
    pending_orders = Order.query.filter_by(order_status="pending").count()
    # In-progress: confirmed, preparing, ready for pickup, out for delivery
    in_progress_statuses = [
        "confirmed", "preparing", "ready for pickup", "out for delivery"
    ]
    in_progress_orders = Order.query.filter(
        Order.order_status.in_(in_progress_statuses)
    ).count()
    delivered_orders = Order.query.filter_by(order_status="delivered").count()

    recent_orders = (
        Order.query.order_by(Order.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "admin/dashboard.html",
        total_items=total_items,
        available_items=available_items,
        unavailable_items=unavailable_items,
        total_categories=total_categories,
        total_orders=total_orders,
        pending_orders=pending_orders,
        in_progress_orders=in_progress_orders,
        delivered_orders=delivered_orders,
        recent_orders=recent_orders,
        order_status_label=_order_status_label,
    )


@admin_bp.route("/menu")
@login_required
@admin_required
def menu_list():
    page = request.args.get("page", 1, type=int)
    per_page = 12
    search = (request.args.get("search") or "").strip()
    category_id = request.args.get("category_id", type=int)

    query = Product.query
    if search:
        query = query.filter(
            Product.name.ilike(f"%{search}%")
            | Product.description.ilike(f"%{search}%")
        )
    if category_id:
        query = query.filter_by(category_id=category_id)

    pagination = query.order_by(Product.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    products = pagination.items
    categories = Category.query.order_by(Category.name).all()

    return render_template(
        "admin/menu_list.html",
        products=products,
        pagination=pagination,
        categories=categories,
        search=search,
        category_id=category_id,
    )


@admin_bp.route("/menu/add", methods=["GET", "POST"])
@login_required
@admin_required
def menu_add():
    categories = Category.query.order_by(Category.name).all()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip()
        category_id = request.form.get("category_id", type=int)
        price = request.form.get("price", type=float)
        is_vegetarian = "is_vegetarian" in request.form
        is_available = "is_available" in request.form
        image_file = request.files.get("image")

        errors = []
        if not name:
            errors.append("Product name is required.")
        if not description:
            errors.append("Description is required.")
        if not category_id:
            errors.append("Category is required.")
        if not price or price <= 0:
            errors.append("Price must be greater than zero.")
        if not image_file or image_file.filename == "":
            errors.append("Product image is required.")
        elif not allowed_file(image_file.filename):
            errors.append("Only JPG, JPEG, PNG and WEBP images are allowed.")
        if not is_vegetarian:
            errors.append("Only vegetarian products can be added.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template(
                "admin/menu_form.html", categories=categories, action="Add"
            )

        filename = secure_filename(image_file.filename)
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(
            os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        ):
            filename = f"{base}_{counter}{ext}"
            counter += 1
        image_file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))

        product = Product(
            name=name,
            description=description,
            price=price,
            category_id=category_id,
            image=filename,
            is_vegetarian=True,  # all products must be vegetarian
            is_available=is_available,
        )
        db.session.add(product)
        db.session.commit()
        flash("Menu item added successfully.", "success")
        return redirect(url_for("admin.menu_list"))

    return render_template(
        "admin/menu_form.html", categories=categories, action="Add"
    )


@admin_bp.route("/menu/edit/<int:id>", methods=["GET", "POST"])
@login_required
@admin_required
def menu_edit(id):
    product = Product.query.get_or_404(id)
    categories = Category.query.order_by(Category.name).all()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip()
        category_id = request.form.get("category_id", type=int)
        price = request.form.get("price", type=float)
        is_vegetarian = "is_vegetarian" in request.form
        is_available = "is_available" in request.form
        image_file = request.files.get("image")

        errors = []
        if not name:
            errors.append("Product name is required.")
        if not description:
            errors.append("Description is required.")
        if not category_id:
            errors.append("Category is required.")
        if not price or price <= 0:
            errors.append("Price must be greater than zero.")
        if not is_vegetarian:
            errors.append("Only vegetarian products can be saved.")

        old_image = product.image

        if image_file and image_file.filename != "":
            if not allowed_file(image_file.filename):
                errors.append("Only JPG, JPEG, PNG and WEBP images are allowed.")
            else:
                filename = secure_filename(image_file.filename)
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(
                    os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
                ):
                    filename = f"{base}_{counter}{ext}"
                    counter += 1
                image_file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))
                product.image = filename
                # Remove the old image only if no other product references it.
                if old_image:
                    other = Product.query.filter(
                        Product.image == old_image, Product.id != id
                    ).first()
                    if not other:
                        old_path = os.path.join(
                            current_app.config["UPLOAD_FOLDER"], old_image
                        )
                        if os.path.exists(old_path):
                            try:
                                os.remove(old_path)
                            except OSError:
                                pass

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template(
                "admin/menu_form.html",
                product=product,
                categories=categories,
                action="Edit",
            )

        product.name = name
        product.description = description
        product.price = price
        product.category_id = category_id
        product.is_vegetarian = True
        product.is_available = is_available
        db.session.commit()
        flash("Menu item updated successfully.", "success")
        return redirect(url_for("admin.menu_list"))

    return render_template(
        "admin/menu_form.html",
        product=product,
        categories=categories,
        action="Edit",
    )


@admin_bp.route("/menu/delete/<int:id>", methods=["POST"])
@login_required
@admin_required
def menu_delete(id):
    product = Product.query.get_or_404(id)
    # Soft-delete: disable the product so historical orders/references are preserved.
    product.is_available = False
    db.session.commit()
    flash(f'"{product.name}" has been disabled. Historical orders are preserved.', "success")
    return redirect(url_for("admin.menu_list"))


@admin_bp.route("/menu/toggle-availability/<int:id>", methods=["POST"])
@login_required
@admin_required
def toggle_availability(id):
    product = Product.query.get_or_404(id)
    product.is_available = not product.is_available
    db.session.commit()
    status = "available" if product.is_available else "unavailable"
    flash(f'"{product.name}" is now {status}.', "success")
    return redirect(url_for("admin.menu_list"))


# ---------------------------------------------------------------------------
# Admin Order Management (Feature 6)
# ---------------------------------------------------------------------------

ORDER_STATUS_LABELS = {
    "pending": "Pending",
    "confirmed": "Confirmed",
    "preparing": "Preparing",
    "ready for pickup": "Ready for Pickup",
    "out for delivery": "Out for Delivery",
    "delivered": "Delivered",
    "cancelled": "Cancelled",
}

FINAL_STATUSES = {"delivered", "cancelled"}


def _order_status_label(status):
    return ORDER_STATUS_LABELS.get((status or "").lower(), (status or "").title())


@admin_bp.route("/orders")
@login_required
@admin_required
def orders_list():
    """List all orders with search, status/payment filters, and pagination."""
    page = request.args.get("page", 1, type=int)
    per_page = 20
    search = (request.args.get("search") or "").strip()
    status_filter = (request.args.get("status") or "").strip().lower()
    payment_filter = (request.args.get("payment") or "").strip().lower()

    query = Order.query

    if search:
        like = f"%{search}%"
        query = query.filter(
            Order.order_number.ilike(like)
            | Order.customer_name.ilike(like)
            | Order.phone.ilike(like)
        )
    if status_filter:
        query = query.filter(Order.order_status.ilike(status_filter))
    if payment_filter:
        query = query.filter(Order.payment_status.ilike(payment_filter))

    pagination = query.order_by(Order.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    orders = pagination.items

    return render_template(
        "admin/orders_list.html",
        orders=orders,
        pagination=pagination,
        search=search,
        status_filter=status_filter,
        payment_filter=payment_filter,
        order_status_label=_order_status_label,
    )


@admin_bp.route("/orders/<order_number>")
@login_required
@admin_required
def order_detail(order_number):
    """Display a single order's customer details, items, and summary."""
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    return render_template(
        "admin/order_detail.html",
        order=order,
        order_status_label=_order_status_label,
    )


@admin_bp.route("/orders/<order_number>/status", methods=["POST"])
@login_required
@admin_required
def order_status_update(order_number):
    """Update an order's status through the allowed forward-only chain."""
    order = Order.query.filter_by(order_number=order_number).first_or_404()

    if not _csrf_valid(request.form.get("csrf_token")):
        flash("Invalid request. Please try again.", "error")
        return redirect(url_for("admin.order_detail", order_number=order_number))

    new_status = (request.form.get("new_status") or "").strip()

    try:
        order.transition_to(new_status)
        db.session.commit()
        flash(
            f"Order {order.order_number} status updated to "
            f"{_order_status_label(order.order_status)}.",
            "success",
        )
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")

    return redirect(url_for("admin.order_detail", order_number=order_number))


@admin_bp.route("/orders/<order_number>/payment", methods=["POST"])
@login_required
@admin_required
def order_payment_update(order_number):
    """Mark a Cash on Delivery order as paid."""
    order = Order.query.filter_by(order_number=order_number).first_or_404()

    if not _csrf_valid(request.form.get("csrf_token")):
        flash("Invalid request. Please try again.", "error")
        return redirect(url_for("admin.order_detail", order_number=order_number))

    if order.payment_method != "cod":
        flash(
            f"Order {order.order_number} is not a Cash on Delivery order, so its "
            f"payment status cannot be changed here.",
            "error",
        )
        return redirect(url_for("admin.order_detail", order_number=order_number))

    if order.payment_status == "paid":
        flash(
            f"Order {order.order_number} is already marked as paid.",
            "error",
        )
        return redirect(url_for("admin.order_detail", order_number=order_number))

    order.payment_status = "paid"
    db.session.commit()
    flash(
        f"Order {order.order_number} marked as paid.", "success"
    )
    return redirect(url_for("admin.order_detail", order_number=order_number))
