from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Order

customer_bp = Blueprint("customer", __name__)

# Order statuses considered "in progress" (active, not yet completed/cancelled).
IN_PROGRESS_STATUSES = [
    "confirmed",
    "preparing",
    "ready for pickup",
    "out for delivery",
]


def customer_required(f):
    """Only authenticated non-admin customers may proceed.

    - Unauthenticated users are redirected to login with a safe `next` so they
      return to this page after logging in.
    - Admins are redirected to the admin dashboard (they never see customer pages).
    - Ordinary customers proceed.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        if current_user.is_admin:
            flash("Admin users cannot access the customer dashboard.", "warning")
            return redirect(url_for("admin.dashboard"))
        return f(*args, **kwargs)
    return decorated


@customer_bp.route("/account")
@customer_required
def dashboard():
    """Customer dashboard: welcome, profile, order summary cards, recent orders."""
    user_id = current_user.id

    total_orders = Order.query.filter_by(user_id=user_id).count()
    pending_orders = Order.query.filter_by(
        user_id=user_id, order_status="pending"
    ).count()
    in_progress_orders = Order.query.filter(
        Order.user_id == user_id,
        Order.order_status.in_(IN_PROGRESS_STATUSES),
    ).count()
    completed_orders = Order.query.filter_by(
        user_id=user_id, order_status="delivered"
    ).count()

    recent_orders = (
        Order.query.filter_by(user_id=user_id)
        .order_by(Order.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "customer/dashboard.html",
        total_orders=total_orders,
        pending_orders=pending_orders,
        in_progress_orders=in_progress_orders,
        completed_orders=completed_orders,
        recent_orders=recent_orders,
    )


@customer_bp.route("/account/orders")
@customer_required
def orders():
    """Customer order history: all of the customer's orders, newest first, paginated."""
    page = request.args.get("page", 1, type=int)
    per_page = 10

    pagination = (
        Order.query.filter_by(user_id=current_user.id)
        .order_by(Order.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    orders = pagination.items

    return render_template(
        "customer/order_history.html",
        orders=orders,
        pagination=pagination,
    )


@customer_bp.route("/account/orders/<order_number>")
@customer_required
def order_detail(order_number):
    """Customer-facing order detail for one of the customer's own orders.

    Queries by both order number and the authenticated user's ID, so a foreign
    or unknown order number returns the project's normal 404.
    """
    order = (
        Order.query.filter_by(order_number=order_number, user_id=current_user.id)
        .first_or_404()
    )

    return render_template("customer/order_detail.html", order=order)
