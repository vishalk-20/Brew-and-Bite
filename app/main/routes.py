from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("main.customer_home"))
    return redirect(url_for("auth.login"))


@main_bp.route("/customer")
def customer_home():
    """Customer homepage / account dashboard."""
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=url_for("main.customer_home")))
    if current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    return render_template("main/customer_home.html")
